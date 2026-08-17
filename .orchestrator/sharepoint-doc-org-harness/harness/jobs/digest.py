from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.actions.archive import ArchiveLane
from harness.actions.inbox import InboxSorter
from harness.config import HarnessConfig, load_correction_rules, match_exclude
from harness.journal.store import ActionJournal

HELPER_FILE_NAMES = {"_redirect_state.json"}


def iter_digest_files(
    *,
    inbox: Path,
    capture_dirs: list[Path],
    exclude_globs: list[str],
    only: list[str] | None = None,
) -> list[Path]:
    """Capture folders recurse. Inbox root is top-level files only."""
    wanted = [item.strip().replace("\\", "/").rstrip("/") for item in (only or []) if item]
    files: list[Path] = []
    seen: set[Path] = set()

    def _add_file(src: Path) -> None:
        if not src.is_file() or src in seen:
            return
        if src.name.lower() in HELPER_FILE_NAMES:
            return
        if match_exclude(src, exclude_globs):
            return
        seen.add(src)
        files.append(src)

    def _add_capture(folder: Path) -> None:
        if not folder.is_dir():
            return
        for src in sorted(folder.rglob("*")):
            _add_file(src)

    if wanted:
        caps_by_name = {folder.name: folder for folder in capture_dirs}
        for token in wanted:
            if token in {"inbox", "00_Inbox"}:
                if inbox.is_dir():
                    for src in sorted(inbox.iterdir()):
                        _add_file(src)
                continue
            folder = caps_by_name.get(token)
            if folder is None:
                folder = next((c for c in capture_dirs if c.as_posix().endswith(token)), None)
            if folder is not None:
                _add_capture(folder)
        return files

    for folder in capture_dirs:
        _add_capture(folder)
    if inbox.is_dir():
        for src in sorted(inbox.iterdir()):
            _add_file(src)
    return files


@dataclass
class DigestReport:
    run_id: str
    started_at: str
    finished_at: str
    inbox_scanned: int = 0
    moved: int = 0
    held: int = 0
    skipped: int = 0
    archived: int = 0
    inbox_active: int = 0
    inbox_ceiling: int = 100
    ceiling_breach: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def count_active_inbox(inbox: Path, exclude_globs: list[str]) -> int:
    if not inbox.is_dir():
        return 0
    n = 0
    for p in inbox.rglob("*"):
        if not p.is_file():
            continue
        if match_exclude(p.relative_to(inbox) if p.is_relative_to(inbox) else p, exclude_globs):
            continue
        # Skip helper subfolders
        if any(part.startswith("_") for part in p.relative_to(inbox).parts[:-1]):
            continue
        n += 1
    return n


def run_digest(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    llm_caller: Callable[..., str] | None = None,
    dry_run: bool = False,
    only: list[str] | None = None,
    limit: int | None = None,
) -> DigestReport:
    """scan → classify → act → report. Fails closed if inference policy invalid."""
    cfg.validate_inference_policy()
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="digest")
    root = cfg.sync_root
    inbox = root / cfg.inbox_rel
    rules = load_correction_rules(cfg.resolve_path(cfg.correction_rules_path))
    report = DigestReport(
        run_id=run_id,
        started_at=started,
        finished_at="",
        inbox_ceiling=cfg.inbox_active_ceiling,
    )

    if dry_run:
        report.notes.append("dry_run")
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.inbox_active = count_active_inbox(inbox, cfg.exclude_globs)
        report.ceiling_breach = cfg.ceiling_enabled and report.inbox_active > report.inbox_ceiling
        report.write(report_path)
        return report

    # Keep manifest beside the journal so pytest tmp journals never share a
    # package-global processed hash set (cutover 2026-08-12 regression).
    manifest_path = Path(journal.path).with_name("processed_manifest.json")
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=rules,
        litellm_base_url=cfg.litellm.base_url,
        model=cfg.litellm.classify_model,
        forbid_host_substrings=cfg.litellm.forbid_host_substrings,
        manifest_path=manifest_path,
        llm_caller=llm_caller,
        readable_names=cfg.readable_names,
        fallback_model=cfg.litellm.fallback_model,
    )
    capture_dirs = [root / rel for rel in cfg.capture_rels()]
    sources = iter_digest_files(
        inbox=inbox,
        capture_dirs=capture_dirs,
        exclude_globs=cfg.exclude_globs,
        only=only,
    )
    if limit is not None:
        sources = sources[: max(0, limit)]
        report.notes.append(f"limit={limit}")
    if only:
        report.notes.append("only=" + ",".join(only))
    for src in sources:
        report.inbox_scanned += 1
        try:
            r = sorter.process_file(src, run_id=run_id)
        except OSError as exc:
            report.skipped += 1
            if len(report.notes) < 20:
                report.notes.append(f"skip_error:{src.name}:{exc.__class__.__name__}")
            continue
        if r.status == "moved":
            report.moved += 1
        elif r.status == "held":
            report.held += 1
        else:
            report.skipped += 1

    if cfg.auto_archive:
        archiver = ArchiveLane(root=root, journal=journal, horizon_days=cfg.horizon_days)
        for folder in root.iterdir() if root.is_dir() else []:
            if not folder.is_dir() or folder.name.startswith("00_") or folder.name.startswith("_"):
                continue
            for src in folder.rglob("*"):
                if not src.is_file() or match_exclude(src, cfg.exclude_globs):
                    continue
                if archiver.should_archive(src):
                    ar = archiver.archive_file(src, run_id=run_id)
                    if ar.status == "archived":
                        report.archived += 1

    report.inbox_active = count_active_inbox(inbox, cfg.exclude_globs)
    report.ceiling_breach = cfg.ceiling_enabled and report.inbox_active > report.inbox_ceiling
    if report.ceiling_breach:
        report.notes.append(
            f"inbox_active={report.inbox_active} exceeds ceiling={report.inbox_ceiling}"
        )
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
