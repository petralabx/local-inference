from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.actions.drain import (
    collect_source_files,
    is_noise_file,
    dest_relative,
    is_secret_file,
    load_drain_map,
    plan_unique_files,
    resolve_dest,
)
from harness.config import HarnessConfig
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move


@dataclass
class DrainReport:
    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    source_root: str
    dest_root: str
    only: list[str]
    scanned: int = 0
    planned: int = 0
    moved: int = 0
    skipped_duplicate: int = 0
    skipped_secret: int = 0
    skipped_noise: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _record_file(report: DrainReport, src: Path, dest: Path | None, status: str) -> None:
    if len(report.files) >= 200:
        return
    report.files.append(
        {
            "src": str(src),
            "dest": str(dest) if dest else "",
            "status": status,
        }
    )


def run_drain(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    source_root: Path | None = None,
    only: list[str] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    map_path: Path | None = None,
) -> DrainReport:
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="drain" + ("-dry" if dry_run else ""))
    dest_root = cfg.sync_root
    src_root = source_root or dest_root.parent
    mapping = load_drain_map(map_path or cfg.resolve_path(cfg.drain_map_path))
    selected = list(only) if only else sorted(mapping)
    report = DrainReport(
        run_id=run_id,
        started_at=started,
        finished_at="",
        dry_run=dry_run,
        source_root=str(src_root),
        dest_root=str(dest_root),
        only=selected,
    )

    candidates = collect_source_files(
        src_root,
        mapping,
        only=selected,
        exclude_globs=cfg.exclude_globs,
    )
    report.scanned = len(candidates)

    usable: list[Path] = []
    for src in candidates:
        if is_noise_file(src):
            report.skipped_noise += 1
            _record_file(report, src, None, "skip_noise")
            continue
        if is_secret_file(src):
            report.skipped_secret += 1
            _record_file(report, src, None, "skip_secret")
            continue
        usable.append(src)

    if limit is not None:
        usable = usable[: max(0, limit)]
        report.notes.append(f"limit={limit}")

    known: set[str] = set()
    manifest = Path(journal.path).with_name("processed_manifest.json")
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        known = set(data.get("sha256") or [])

    decisions = plan_unique_files(
        usable,
        source_root=src_root,
        mapping=mapping,
        known_hashes=known,
    )
    for decision in decisions:
        dest = dest_root / dest_relative(
            str(decision.src.relative_to(src_root)),
            decision.dest_home,
        )
        if dest.exists():
            try:
                if content_hash(dest) == decision.sha256:
                    report.skipped_duplicate += 1
                    _record_file(report, decision.src, dest, "skip_duplicate")
                    continue
            except OSError:
                pass
            dest = resolve_dest(
                decision.src,
                source_root=src_root,
                dest_root=dest_root,
                dest_home=decision.dest_home,
            )
        if decision.status == "skip_unreadable":
            report.skipped_noise += 1
            _record_file(report, decision.src, dest, "skip_unreadable")
            continue
        if decision.status == "skip_duplicate":
            report.skipped_duplicate += 1
            _record_file(report, decision.src, dest, "skip_duplicate")
            continue
        report.planned += 1
        if dry_run:
            _record_file(report, decision.src, dest, "plan")
            continue
        try:
            apply_move(decision.src, dest)
            journal.record(
                run_id,
                "move",
                {
                    "from": str(decision.src),
                    "to": str(dest),
                    "sha256": decision.sha256,
                    "classification": "drain_map",
                },
            )
            known.add(decision.sha256)
            report.moved += 1
            _record_file(report, decision.src, dest, "moved")
        except OSError as exc:
            report.errors += 1
            report.notes.append(f"{decision.src}: {exc}")
            _record_file(report, decision.src, dest, "error")

    if not dry_run and known:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"sha256": sorted(known)}, indent=2), encoding="utf-8")

    if dry_run:
        report.notes.append("dry_run")
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
