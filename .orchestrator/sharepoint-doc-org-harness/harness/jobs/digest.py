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
    )
    scan_roots = [inbox]
    for rel in cfg.capture_rels():
        cap = root / rel
        if cap.is_dir() and cap not in scan_roots:
            scan_roots.append(cap)
    if inbox.is_dir() or any(p.is_dir() for p in scan_roots):
        seen: set[Path] = set()
        for folder in scan_roots:
            if not folder.is_dir():
                continue
            for src in sorted(folder.iterdir()):
                if not src.is_file() or src in seen:
                    continue
                seen.add(src)
                if match_exclude(src, cfg.exclude_globs):
                    continue
                report.inbox_scanned += 1
                r = sorter.process_file(src, run_id=run_id)
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
