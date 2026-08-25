from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.classify.router import ALLOWED_HOMES
from harness.config import HarnessConfig, load_correction_rules
from harness.graph.drive_client import GraphDriveClient
from harness.jobs.relabel import iter_relabel_files
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger
from harness.stamp.harvest import HarvestStamp, identity_from_path


@dataclass
class StampReport:
    run_id: str
    started_at: str
    finished_at: str
    scanned: int = 0
    stamped: int = 0
    skipped: int = 0
    columns_written: int = 0
    columns_skipped: int = 0
    embedded: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def run_stamp(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    graph: GraphDriveClient | None = None,
    limit: int | None = None,
) -> StampReport:
    """Metadata-only backfill of Title + Party/Prefix/Home. Does not rename."""
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="stamp")
    root = cfg.sync_root
    ledger = DocumentLedger(Path(journal.path))
    report = StampReport(run_id=run_id, started_at=started, finished_at="")
    stamper = HarvestStamp(
        journal=journal,
        graph=graph,
        rules=load_correction_rules(cfg.resolve_path(cfg.correction_rules_path)),
        ledger=ledger,
        exclude_globs=cfg.exclude_globs,
    )
    if graph is None:
        report.notes.append("graph_offline")
    elif not stamper.ensure_site_columns():
        report.notes.append("graph_columns_skipped")
    sources = iter_relabel_files(root, cfg.exclude_globs)
    if limit is not None:
        sources = sources[: max(0, limit)]
        report.notes.append(f"limit={limit}")
    for src in sources:
        report.scanned += 1
        try:
            try:
                home_part = src.relative_to(root).parts[0]
            except ValueError:
                home_part = ""
            if home_part and home_part not in ALLOWED_HOMES:
                report.skipped += 1
                continue
            title, prefix, home = identity_from_path(src, root=root, ledger=ledger)
            result = stamper.apply(
                src,
                run_id=run_id,
                prefix=prefix,
                home=home,
                title=title,
            )
            if result.skipped:
                report.skipped += 1
                continue
            report.stamped += 1
            if result.columns_written:
                report.columns_written += 1
            if result.columns_skipped:
                report.columns_skipped += 1
            if result.embedded.get("written"):
                report.embedded += 1
        except OSError as exc:
            report.errors += 1
            if len(report.notes) < 20:
                report.notes.append(f"{src.name}:{exc.__class__.__name__}")
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
