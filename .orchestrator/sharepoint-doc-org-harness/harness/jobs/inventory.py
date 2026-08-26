from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.actions.inventory import (
    STATUS_ALREADY,
    STATUS_CANDIDATE,
    STATUS_SKIP_CODE,
    STATUS_SKIP_SECRET,
    InventoryHit,
    load_inventory_roots,
    merge_roots,
    walk_inventory_roots,
)
from harness.config import HarnessConfig
from harness.journal.store import ActionJournal


@dataclass
class InventoryReport:
    run_id: str
    started_at: str
    finished_at: str
    sync_root: str
    roots: list[str]
    scanned: int = 0
    candidate_to_consume: int = 0
    skip_code: int = 0
    skip_secret: int = 0
    already_in_vince_personal: int = 0
    skipped_noise: int = 0
    copied: bool = False
    uploaded: bool = False
    missing_roots: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _hit_row(hit: InventoryHit) -> dict[str, str]:
    row = {
        "path": str(hit.path),
        "status": hit.status,
        "root": str(hit.root),
        "kind": hit.kind,
        "sha256": hit.sha256,
    }
    return row


def run_inventory(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    roots: list[str] | None = None,
    roots_file: Path | None = None,
    limit: int | None = None,
) -> InventoryReport:
    """Report leftover document files. Does not copy, move, or upload."""
    started = datetime.now(timezone.utc).isoformat()
    if roots_file is not None and not roots_file.is_file():
        raise ValueError(f"inventory roots file not found: {roots_file}")
    file_roots = load_inventory_roots(roots_file) if roots_file else []
    selected = merge_roots(roots, file_roots)
    if not selected:
        raise ValueError("inventory requires at least one --root or --roots-file entry")
    run_id = journal.start_run(note="inventory")
    sync_root = cfg.sync_root
    extra_tokens = list(cfg.skip_code_path_tokens)
    hits, missing, skipped_noise = walk_inventory_roots(
        [Path(item) for item in selected],
        sync_root=sync_root,
        exclude_globs=cfg.exclude_globs,
        extra_tokens=extra_tokens,
        limit=limit,
    )
    report = InventoryReport(
        run_id=run_id,
        started_at=started,
        finished_at="",
        sync_root=str(sync_root),
        roots=selected,
        skipped_noise=skipped_noise,
        missing_roots=missing,
        copied=False,
        uploaded=False,
    )
    file_hits = [hit for hit in hits if hit.kind == "file"]
    report.scanned = len(file_hits)
    for hit in hits:
        if hit.status == STATUS_CANDIDATE:
            report.candidate_to_consume += 1
        elif hit.status == STATUS_SKIP_CODE:
            report.skip_code += 1
        elif hit.status == STATUS_SKIP_SECRET:
            report.skip_secret += 1
        elif hit.status == STATUS_ALREADY:
            report.already_in_vince_personal += 1
        report.files.append(_hit_row(hit))
    if missing:
        report.notes.append("missing_roots")
    if limit is not None:
        report.notes.append(f"limit={limit}")
    report.notes.append("report_only")
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
