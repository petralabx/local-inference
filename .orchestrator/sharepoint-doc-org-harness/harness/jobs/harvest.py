from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.actions.drain import is_noise_file, is_secret_file
from harness.config import HarnessConfig, load_correction_rules, match_exclude
from harness.graph.drive_client import GraphConflictError, GraphDriveClient, GraphOfflineError
from harness.graph.folder_lister import FolderLister
from harness.jobs.relabel import CAPTURE_DIR_NAMES, HELPER_FILE_NAMES, SKIP_DIR_NAMES
from harness.jobs.stamp import homes_for_stamp
from harness.jobs.sync_audit import (
    default_report_path,
    run_sync_audit,
    should_skip_relative,
)
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger
from harness.stamp.harvest import HarvestStamp, identity_from_path


class HarvestApplyBlocked(RuntimeError):
    """Raised when --apply would move local OneDrive files off-box."""


def guard_harvest_apply(*, apply: bool, would_move_local: bool = False) -> None:
    """Graph-only apply is allowed on Linux/VTA. Local OneDrive moves are not."""
    if not apply:
        return
    if would_move_local and sys.platform != "win32":
        raise HarvestApplyBlocked(
            "refusing --apply that would move local OneDrive files from a "
            "non-Windows host (use Graph upload, not Explorer/OneDrive moves)"
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _posix(rel: str) -> str:
    return rel.replace("\\", "/").strip("/")


def load_local_only(audit_report: Path) -> list[dict[str, Any]]:
    data = json.loads(audit_report.read_text(encoding="utf-8"))
    rows = data.get("local_only") or []
    if not isinstance(rows, list):
        raise ValueError(f"audit report local_only must be a list: {audit_report}")
    return [row for row in rows if isinstance(row, dict)]


@dataclass
class HarvestReport:
    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    apply: bool
    replace: bool
    scanned: int = 0
    planned: int = 0
    uploaded: int = 0
    skipped_identical: int = 0
    skipped_secret: int = 0
    skipped_code: int = 0
    stamped: int = 0
    columns_written: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _skip_entry(rel: str, *, exclude_globs: list[str]) -> str:
    path = Path(_posix(rel))
    if any(part in CAPTURE_DIR_NAMES for part in path.parts):
        return "capture"
    if should_skip_relative(rel, exclude_globs=exclude_globs, is_dir=False):
        if is_secret_file(path):
            return "secret"
        if match_exclude(path, exclude_globs) or any(
            part.lower() in {"node_modules", ".git", "agentic-swarm"} for part in path.parts
        ):
            return "code"
        if path.name.lower() in HELPER_FILE_NAMES or is_noise_file(path):
            return "noise"
        if any(part.lower() in SKIP_DIR_NAMES for part in path.parts):
            return "noise"
        return "exclude"
    if is_secret_file(path):
        return "secret"
    if match_exclude(path, exclude_globs):
        return "code"
    return ""


def _record(report: HarvestReport, row: dict[str, Any]) -> None:
    if len(report.files) < 200:
        report.files.append(row)


def run_harvest(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    graph: GraphDriveClient | None = None,
    apply: bool = False,
    replace: bool = False,
    only: list[str] | None = None,
    limit: int | None = None,
    audit_report: Path | None = None,
    local_only: list[dict[str, Any]] | None = None,
    lister: FolderLister | None = None,
) -> HarvestReport:
    """Graph-upload local_only files, then stamp. Additive. Does not delete or fold."""
    guard_harvest_apply(apply=apply, would_move_local=False)
    started = _utc_now()
    dry_run = not apply
    run_id = journal.start_run(note="harvest" if apply else "harvest-dry")
    report = HarvestReport(
        run_id=run_id,
        started_at=started,
        finished_at="",
        dry_run=dry_run,
        apply=apply,
        replace=replace,
        notes=[
            "graph_upload_additive",
            "no_onedrive_moves",
            "no_delete",
            "fold_not_in_this_job",
        ],
    )
    if dry_run:
        report.notes.append("dry_run")
    if only:
        report.notes.append("only=" + ",".join(homes_for_stamp(only)))
    if limit is not None:
        report.notes.append(f"limit={limit}")

    rows = local_only
    if rows is None and audit_report is not None:
        rows = load_local_only(audit_report)
        report.notes.append(f"audit_report={audit_report}")
    if rows is None:
        if lister is None:
            report.errors += 1
            report.notes.append("missing_local_only_source")
            report.finished_at = _utc_now()
            report.write(report_path)
            return report
        audit_path = default_report_path()
        audit = run_sync_audit(
            cfg=cfg,
            lister=lister,
            report_path=audit_path,
            dry_run=True,
            only=only,
        )
        rows = list(audit.local_only)
        report.notes.append(f"live_compare={audit_path}")

    prefixes = [_posix(item) for item in (only or []) if item]
    ledger = DocumentLedger(Path(journal.path))
    stamper = HarvestStamp(
        journal=journal,
        graph=graph,
        rules=load_correction_rules(cfg.resolve_path(cfg.correction_rules_path)),
        ledger=ledger,
        exclude_globs=cfg.exclude_globs,
    )

    planned: list[tuple[str, Path, dict[str, Any]]] = []
    for row in rows:
        rel = _posix(str(row.get("path") or ""))
        if not rel:
            continue
        if prefixes and not any(rel == p or rel.startswith(p + "/") for p in prefixes):
            continue
        report.scanned += 1
        reason = _skip_entry(rel, exclude_globs=cfg.exclude_globs)
        if reason == "secret":
            report.skipped_secret += 1
            _record(report, {"path": rel, "status": "skipped_secret"})
            continue
        if reason == "code":
            report.skipped_code += 1
            _record(report, {"path": rel, "status": "skipped_code"})
            continue
        if reason:
            _record(report, {"path": rel, "status": f"skipped_{reason}"})
            continue
        local = cfg.sync_root.joinpath(*rel.split("/"))
        if not local.is_file():
            report.errors += 1
            _record(report, {"path": rel, "status": "missing_local"})
            continue
        planned.append((rel, local, row))

    if limit is not None:
        planned = planned[: max(0, limit)]
    report.planned = len(planned)

    if apply and graph is None:
        report.errors += 1
        report.notes.append("graph_unavailable: run harness graph-login on VTA")
        report.finished_at = _utc_now()
        report.write(report_path)
        return report

    for rel, local, _row in planned:
        if dry_run:
            _record(report, {"path": rel, "status": "plan", "size": local.stat().st_size})
            continue
        try:
            result = graph.upload_file(local, rel, replace=replace)  # type: ignore[union-attr]
            status = str(result.get("status") or "uploaded")
            if status == "skipped_identical":
                report.skipped_identical += 1
            else:
                report.uploaded += 1
            journal.record(
                run_id,
                "upload",
                {"path": rel, "status": status, "size": result.get("size"), "mode": result.get("mode")},
            )
            title, prefix, home = identity_from_path(local, root=cfg.sync_root, ledger=ledger)
            stamped = stamper.apply(
                local,
                run_id=run_id,
                prefix=prefix,
                home=home,
                title=title,
            )
            if not stamped.skipped:
                report.stamped += 1
            if stamped.columns_written:
                report.columns_written += 1
            _record(
                report,
                {
                    "path": rel,
                    "status": status,
                    "stamped": not bool(stamped.skipped),
                    "columns_written": stamped.columns_written,
                    "columns_skip_reason": stamped.columns_skip_reason,
                },
            )
        except GraphConflictError as exc:
            report.errors += 1
            _record(report, {"path": rel, "status": "conflict", "error": str(exc)})
            if len(report.notes) < 40:
                report.notes.append(f"conflict:{rel}:{exc}")
        except GraphOfflineError as exc:
            report.errors += 1
            _record(report, {"path": rel, "status": "graph_error", "error": str(exc)})
            if len(report.notes) < 40:
                report.notes.append(f"graph:{rel}:{exc}")
        except OSError as exc:
            report.errors += 1
            _record(report, {"path": rel, "status": "error", "error": exc.__class__.__name__})

    report.finished_at = _utc_now()
    report.write(report_path)
    return report
