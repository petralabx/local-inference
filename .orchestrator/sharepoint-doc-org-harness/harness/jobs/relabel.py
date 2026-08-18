from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.actions.drain import is_noise_file, is_secret_file
from harness.actions.inbox import InboxSorter
from harness.classify.router import ALLOWED_HOMES
from harness.config import HarnessConfig, load_correction_rules, load_taxonomy, match_exclude
from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger, DocumentRecord
from harness.naming import ORGANIZER_NAME_RE, is_organizer_name

CAPTURE_DIR_NAMES = {
    "_from_desktop",
    "_from_documents",
    "_from_downloads",
    "_from_mail",
}
SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    ".trash",
    ".trashes",
}
HELPER_FILE_NAMES = {"_redirect_state.json"}


def _homes_for_relabel() -> list[str]:
    homes = sorted(ALLOWED_HOMES)
    return [h for h in homes if h != "00_Inbox"] + [h for h in homes if h == "00_Inbox"]


def iter_relabel_files(root: Path, exclude_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for home in _homes_for_relabel():
        folder = root / home
        if not folder.is_dir():
            continue
        for src in folder.rglob("*"):
            if not src.is_file():
                continue
            if src.name.lower() in HELPER_FILE_NAMES or is_noise_file(src):
                continue
            if is_secret_file(src):
                continue
            if any(part.lower() in SKIP_DIR_NAMES for part in src.parts):
                continue
            if any(part in CAPTURE_DIR_NAMES for part in src.parts):
                continue
            if match_exclude(src, exclude_globs):
                continue
            files.append(src)
    return files


@dataclass
class RelabelReport:
    run_id: str
    started_at: str
    finished_at: str
    scanned: int = 0
    renamed: int = 0
    ledger_only: int = 0
    held: int = 0
    skipped: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def run_relabel(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    llm_caller: Callable[..., str] | None = None,
    limit: int | None = None,
) -> RelabelReport:
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="relabel")
    root = cfg.sync_root
    type_by_prefix = load_taxonomy(cfg.resolve_path(cfg.taxonomy_path))
    ledger = DocumentLedger(Path(journal.path))
    report = RelabelReport(run_id=run_id, started_at=started, finished_at="")
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=load_correction_rules(cfg.resolve_path(cfg.correction_rules_path)),
        litellm_base_url=cfg.litellm.base_url,
        model=cfg.litellm.classify_model,
        forbid_host_substrings=cfg.litellm.forbid_host_substrings,
        manifest_path=Path(journal.path).with_name("processed_manifest.json"),
        llm_caller=llm_caller,
        readable_names=cfg.readable_names,
        organizer_names=True,
        fallback_model=cfg.litellm.fallback_model,
        ledger=ledger,
        type_by_prefix=type_by_prefix,
    )
    sources = iter_relabel_files(root, cfg.exclude_globs)
    if limit is not None:
        sources = sources[: max(0, limit)]
        report.notes.append(f"limit={limit}")
    for src in sources:
        report.scanned += 1
        try:
            if is_organizer_name(src.name) and ledger.get(content_hash(src)) is not None:
                report.skipped += 1
                continue
            if is_organizer_name(src.name):
                parsed = ORGANIZER_NAME_RE.match(src.name)
                digest = content_hash(src)
                try:
                    home = src.relative_to(root).parts[0]
                except ValueError:
                    home = "00_Inbox"
                assert parsed is not None
                ledger.upsert(
                    DocumentRecord(
                        sha256=digest,
                        title=parsed.group("title"),
                        prefix=parsed.group("prefix"),
                        doc_type=type_by_prefix.get(parsed.group("prefix"), parsed.group("prefix")),
                        doc_date=parsed.group("date"),
                        version=int(parsed.group("ver")),
                        home=home,
                        current_path=str(src),
                        source="relabel_parse",
                    )
                )
                report.ledger_only += 1
                continue
            result = sorter.process_file(
                src, run_id=run_id, ignore_manifest=True, keep_folder=True
            )
            if result.status == "held":
                report.held += 1
            elif result.status == "moved":
                if result.dest is not None and result.dest.resolve() != src.resolve():
                    report.renamed += 1
                else:
                    report.ledger_only += 1
            else:
                report.skipped += 1
        except OSError as exc:
            report.errors += 1
            if len(report.notes) < 20:
                report.notes.append(f"{src.name}:{exc.__class__.__name__}")
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
