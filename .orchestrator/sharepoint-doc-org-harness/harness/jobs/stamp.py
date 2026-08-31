from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.actions.drain import is_noise_file, is_secret_file
from harness.classify.router import ALLOWED_HOMES
from harness.config import HarnessConfig, load_correction_rules, match_exclude
from harness.graph.drive_client import GraphDriveClient
from harness.jobs.relabel import (
    CAPTURE_DIR_NAMES,
    HELPER_FILE_NAMES,
    SKIP_DIR_NAMES,
    homes_for_relabel,
    walk_files_tolerant,
)
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger
from harness.stamp.harvest import HarvestStamp, identity_from_library_path, identity_from_path


class UnsafeOnlyPath(ValueError):
    """--only path would escape the sync root."""


def safe_rel(rel: str) -> str:
    raw = rel.replace("\\", "/")
    if Path(rel).is_absolute() or raw.startswith("/") or raw.startswith("~"):
        raise UnsafeOnlyPath(f"unsafe relative path: {rel}")
    cleaned = raw.strip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise UnsafeOnlyPath(f"unsafe relative path: {rel}")
    return cleaned


def homes_for_stamp(only: list[str] | None = None) -> list[str]:
    if not only:
        return homes_for_relabel()
    return [safe_rel(item) for item in only if item]


def folder_under_root(root: Path, rel: str) -> Path | None:
    try:
        cleaned = safe_rel(rel)
    except UnsafeOnlyPath:
        return None
    folder = (root / cleaned).resolve()
    try:
        folder.relative_to(root.resolve())
    except ValueError:
        return None
    return folder


def iter_stamp_files(
    root: Path,
    exclude_globs: list[str],
    *,
    only: list[str] | None = None,
) -> Iterator[Path]:
    """Walk 00–06 homes (or --only) one folder at a time. Leftover trees are not folded."""
    for home in homes_for_stamp(only):
        folder = folder_under_root(root, home)
        if folder is None or not folder.is_dir():
            continue
        for src in walk_files_tolerant(folder):
            try:
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
                yield src
            except OSError:
                continue


def _library_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix().lstrip("/")


def _walk_graph_paths(graph: GraphDriveClient, folder: str) -> Iterator[str]:
    walk = getattr(graph, "walk_folder", None)
    if walk is None:
        return
    for row in walk(folder):
        if isinstance(row, str):
            yield row.replace("\\", "/").strip("/")
            continue
        if isinstance(row, dict):
            rel = str(row.get("libraryPath") or row.get("name") or "").replace("\\", "/").strip("/")
            if rel:
                yield rel


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
    skip_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _record_skip(report: StampReport, rel: str, reason: str) -> None:
    if not reason:
        return
    if len(report.skip_reasons) < 80:
        report.skip_reasons.append(f"{rel}:{reason}")
    if len(report.notes) < 40:
        note = f"columns_skipped:{rel}:{reason}"
        if note not in report.notes:
            report.notes.append(note)


def run_stamp(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    graph: GraphDriveClient | None = None,
    limit: int | None = None,
    only: list[str] | None = None,
    backfill: bool = False,
) -> StampReport:
    """Metadata-only backfill of Title + Party/Prefix/Home. Does not rename."""
    if backfill:
        return run_stamp_backfill(
            cfg=cfg,
            journal=journal,
            report_path=report_path,
            graph=graph,
            limit=limit,
            only=only,
        )
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
    try:
        homes = homes_for_stamp(only)
    except UnsafeOnlyPath as exc:
        report.errors += 1
        report.notes.append(str(exc))
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.write(report_path)
        return report
    if graph is None:
        report.notes.append("graph_offline")
    elif not stamper.ensure_site_columns():
        report.notes.append("graph_columns_skipped")
    if limit is not None:
        report.notes.append(f"limit={limit}")
    if only:
        report.notes.append("only=" + ",".join(homes))

    seen: set[str] = set()

    def _budget_left() -> bool:
        if limit is None:
            return True
        return report.scanned < max(0, limit)

    for src in iter_stamp_files(root, cfg.exclude_globs, only=only):
        if not _budget_left():
            break
        report.scanned += 1
        rel = _library_rel(src, root)
        seen.add(rel.casefold())
        try:
            try:
                home_part = src.relative_to(root).parts[0]
            except ValueError:
                home_part = ""
            if home_part and home_part not in ALLOWED_HOMES and not only:
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
                if result.columns_skipped:
                    report.columns_skipped += 1
                _record_skip(report, rel, result.skipped or result.columns_skip_reason)
                continue
            report.stamped += 1
            if result.columns_written:
                report.columns_written += 1
            if result.columns_skipped:
                report.columns_skipped += 1
                _record_skip(report, rel, result.columns_skip_reason)
            if result.embedded.get("written"):
                report.embedded += 1
        except OSError as exc:
            report.errors += 1
            if len(report.notes) < 20:
                report.notes.append(f"{src.name}:{exc.__class__.__name__}")

    if graph is not None:
        for home in homes:
            if not _budget_left():
                break
            try:
                remote_paths = list(_walk_graph_paths(graph, home))
            except Exception as exc:  # noqa: BLE001 — keep stamping other homes
                report.errors += 1
                report.notes.append(f"walk:{home}:{exc.__class__.__name__}:{exc}")
                continue
            for rel in remote_paths:
                if not _budget_left():
                    break
                key = rel.casefold()
                if key in seen:
                    continue
                name = Path(rel).name
                if name.lower() in HELPER_FILE_NAMES or is_noise_file(Path(rel)):
                    continue
                if is_secret_file(Path(rel)):
                    report.skipped += 1
                    continue
                if any(part.lower() in SKIP_DIR_NAMES for part in Path(rel).parts):
                    continue
                if any(part in CAPTURE_DIR_NAMES for part in Path(rel).parts):
                    continue
                if match_exclude(Path(rel), cfg.exclude_globs):
                    continue
                report.scanned += 1
                seen.add(key)
                title, prefix, home_id = identity_from_library_path(rel)
                result = stamper.apply_remote(
                    rel,
                    run_id=run_id,
                    prefix=prefix,
                    home=home_id,
                    title=title,
                )
                if result.skipped:
                    report.skipped += 1
                    if result.columns_skipped:
                        report.columns_skipped += 1
                    _record_skip(report, rel, result.skipped or result.columns_skip_reason)
                    continue
                if result.columns_written:
                    report.stamped += 1
                    report.columns_written += 1
                else:
                    report.skipped += 1
                    report.columns_skipped += 1
                    _record_skip(report, rel, result.columns_skip_reason or "columns_unwritten")
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report


def run_stamp_backfill(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    graph: GraphDriveClient | None = None,
    limit: int | None = None,
    only: list[str] | None = None,
) -> StampReport:
    """Retry Graph 404 stamps by current path or stored item id. No rename."""
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="stamp-backfill")
    root = cfg.sync_root
    ledger = DocumentLedger(Path(journal.path))
    report = StampReport(run_id=run_id, started_at=started, finished_at="")
    report.notes.append("stamp_backfill")
    stamper = HarvestStamp(
        journal=journal,
        graph=graph,
        rules=load_correction_rules(cfg.resolve_path(cfg.correction_rules_path)),
        ledger=ledger,
        exclude_globs=cfg.exclude_globs,
    )
    try:
        prefixes = homes_for_stamp(only) if only else []
    except UnsafeOnlyPath as exc:
        report.errors += 1
        report.notes.append(str(exc))
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.write(report_path)
        return report
    if graph is None:
        report.notes.append("graph_offline")
    if only:
        report.notes.append("only=" + ",".join(prefixes))
    if limit is not None:
        report.notes.append(f"limit={limit}")

    seen: set[str] = set()
    for action in journal.list_actions_by_type("stamp"):
        if limit is not None and report.scanned >= max(0, limit):
            break
        payload = action.payload
        reason = str(payload.get("columns_skip_reason") or payload.get("skipped") or "")
        if "404" not in reason and payload.get("skipped") != "graph_404":
            continue
        raw_path = str(payload.get("path") or "")
        if not raw_path:
            continue
        src = Path(raw_path)
        if not src.is_file():
            digest = str(payload.get("sha256_after") or payload.get("sha256_before") or "")
            rec = ledger.get(digest) if digest and hasattr(ledger, "get") else None
            if rec is not None and rec.current_path:
                src = Path(rec.current_path)
        if not src.is_file():
            report.skipped += 1
            _record_skip(report, raw_path, "missing_local")
            continue
        try:
            rel = src.relative_to(root).as_posix()
        except ValueError:
            rel = src.as_posix()
        if prefixes and not any(rel == p or rel.startswith(p + "/") for p in prefixes):
            continue
        key = str(src)
        if key in seen:
            continue
        seen.add(key)
        report.scanned += 1
        title, prefix, home = identity_from_path(src, root=root, ledger=ledger)
        result = stamper.apply(
            src,
            run_id=run_id,
            prefix=prefix,
            home=home,
            title=title,
            item_id=str(payload.get("item_id") or "") or None,
            previous_path=str(payload.get("previous_path") or payload.get("path") or "") or None,
        )
        if result.skipped:
            report.skipped += 1
            if result.columns_skipped:
                report.columns_skipped += 1
            _record_skip(report, rel, result.skipped or result.columns_skip_reason)
            continue
        report.stamped += 1
        if result.columns_written:
            report.columns_written += 1
        if result.columns_skipped:
            report.columns_skipped += 1
            _record_skip(report, rel, result.columns_skip_reason)
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
