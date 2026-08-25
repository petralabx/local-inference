from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.actions.drain import is_noise_file, is_secret_file
from harness.config import HarnessConfig, match_exclude
from harness.graph.folder_lister import (
    FolderLister,
    FolderListing,
    RemoteItem,
    child_rel,
    posix_rel,
)
from harness.identity import content_hash
from harness.jobs.relabel import HELPER_FILE_NAMES, SKIP_DIR_NAMES

DEFAULT_REPORT_REL = "data/reports/sync-audit.json"

# Search / ItemCount are not completeness checks. This job walks folders.
AUDIT_NOTES = [
    "report_only",
    "walk_by_folder",
    "sharepoint_itemcount_is_not_recursive",
    "search_api_is_not_a_completeness_check",
]


def default_report_path() -> Path:
    from harness.config import PACKAGE_ROOT

    return PACKAGE_ROOT / DEFAULT_REPORT_REL


@dataclass
class AuditEntry:
    path: str
    name: str
    size: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PathMismatch:
    name: str
    local_path: str
    server_path: str
    local_size: int | None = None
    server_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HashMismatch:
    path: str
    local_sha256: str
    server_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SyncAuditReport:
    run_id: str
    started_at: str
    finished_at: str
    backend: str
    sync_root: str
    dry_run: bool
    hashes: bool
    local_files: int = 0
    server_files: int = 0
    folders_walked: int = 0
    skipped: int = 0
    local_only: list[dict[str, Any]] = field(default_factory=list)
    server_only: list[dict[str, Any]] = field(default_factory=list)
    path_mismatches: list[dict[str, Any]] = field(default_factory=list)
    hash_mismatches: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def discrepancy_count(self) -> int:
        return (
            len(self.local_only)
            + len(self.server_only)
            + len(self.path_mismatches)
            + len(self.hash_mismatches)
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["discrepancy_count"] = self.discrepancy_count
        return data

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def should_skip_relative(rel: str, *, exclude_globs: list[str], is_dir: bool = False) -> bool:
    path = Path(posix_rel(rel)) if rel else Path(".")
    parts = [p.lower() for p in path.parts if p not in {".", ""}]
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if is_secret_file(path):
        return True
    if not is_dir:
        if path.name.lower() in HELPER_FILE_NAMES or is_noise_file(path):
            return True
    if exclude_globs and match_exclude(path, exclude_globs):
        return True
    return False


def _list_local_children(
    folder: Path,
    folder_rel: str,
    *,
    exclude_globs: list[str],
) -> tuple[dict[str, AuditEntry], dict[str, str], list[str], int]:
    files: dict[str, AuditEntry] = {}
    dirs: dict[str, str] = {}
    errors: list[str] = []
    skipped = 0
    if not folder.is_dir():
        return files, dirs, errors, skipped
    try:
        with os.scandir(folder) as it:
            entries = list(it)
    except OSError as exc:
        errno = getattr(exc, "errno", None) or getattr(exc, "winerror", None)
        errors.append(f"{posix_rel(folder_rel) or '.'}:OSError:{errno}:{exc.__class__.__name__}")
        return files, dirs, errors, skipped
    for entry in entries:
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
        except OSError:
            skipped += 1
            continue
        child = child_rel(folder_rel, entry.name)
        if should_skip_relative(child, exclude_globs=exclude_globs, is_dir=is_dir):
            skipped += 1
            continue
        key = entry.name.casefold()
        if is_dir:
            dirs[key] = entry.name
        elif is_file:
            try:
                size = int(entry.stat(follow_symlinks=False).st_size)
            except OSError:
                size = None
            files[key] = AuditEntry(path=child, name=entry.name, size=size)
    return files, dirs, errors, skipped


def _remote_maps(
    listing: FolderListing,
    *,
    exclude_globs: list[str],
) -> tuple[dict[str, RemoteItem], dict[str, RemoteItem], int]:
    files: dict[str, RemoteItem] = {}
    folders: dict[str, RemoteItem] = {}
    skipped = 0
    for item in listing.files:
        if should_skip_relative(item.posix, exclude_globs=exclude_globs, is_dir=False):
            skipped += 1
            continue
        files[item.name.casefold()] = item
    for item in listing.folders:
        if should_skip_relative(item.posix, exclude_globs=exclude_globs, is_dir=True):
            skipped += 1
            continue
        folders[item.name.casefold()] = item
    return files, folders, skipped


def _pair_path_mismatches(
    unmatched_local: list[AuditEntry],
    unmatched_server: list[RemoteItem],
) -> tuple[list[PathMismatch], list[AuditEntry], list[RemoteItem]]:
    local_by_name: dict[str, list[AuditEntry]] = defaultdict(list)
    server_by_name: dict[str, list[RemoteItem]] = defaultdict(list)
    for item in unmatched_local:
        local_by_name[item.name.casefold()].append(item)
    for item in unmatched_server:
        server_by_name[item.name.casefold()].append(item)
    for bucket in local_by_name.values():
        bucket.sort(key=lambda row: row.path.lower())
    for bucket in server_by_name.values():
        bucket.sort(key=lambda row: row.posix.lower())
    mismatches: list[PathMismatch] = []
    local_only: list[AuditEntry] = []
    server_only: list[RemoteItem] = []
    for name in sorted(set(local_by_name) | set(server_by_name)):
        locs = local_by_name.get(name, [])
        rems = server_by_name.get(name, [])
        while locs and rems:
            local = locs.pop(0)
            remote = rems.pop(0)
            mismatches.append(
                PathMismatch(
                    name=local.name,
                    local_path=local.path,
                    server_path=remote.posix,
                    local_size=local.size,
                    server_size=remote.size,
                )
            )
        local_only.extend(locs)
        server_only.extend(rems)
    return mismatches, local_only, server_only


def run_sync_audit(
    *,
    cfg: HarnessConfig,
    lister: FolderLister,
    report_path: Path | None = None,
    dry_run: bool = False,
    hashes: bool = False,
    only: list[str] | None = None,
    hasher: Callable[[Path], str] = content_hash,
) -> SyncAuditReport:
    """Compare local Vince Personal tree to SharePoint. Report only — no mutate."""
    started = _utc_now()
    root = cfg.sync_root
    compare_hashes = bool(hashes) and not dry_run
    report = SyncAuditReport(
        run_id=uuid.uuid4().hex,
        started_at=started,
        finished_at="",
        backend=getattr(lister, "backend", "unknown"),
        sync_root=str(root),
        dry_run=bool(dry_run),
        hashes=compare_hashes,
        notes=list(AUDIT_NOTES),
    )
    if dry_run:
        report.notes.append("dry_run")
    if hashes and dry_run:
        report.notes.append("hashes_skipped_dry_run")
    if not root.exists():
        report.errors.append(f"missing_sync_root:{root}")
        report.finished_at = _utc_now()
        path = report_path or default_report_path()
        report.write(path)
        return report

    starts = [posix_rel(item) for item in (only or []) if item]
    if not starts:
        starts = [""]
    else:
        report.notes.append("only=" + ",".join(starts))

    unmatched_local: list[AuditEntry] = []
    unmatched_server: list[RemoteItem] = []
    seen_folders: set[str] = set()

    def walk(folder_rel: str) -> None:
        rel = posix_rel(folder_rel)
        if rel in seen_folders:
            return
        seen_folders.add(rel)
        if rel and should_skip_relative(rel, exclude_globs=cfg.exclude_globs, is_dir=True):
            report.skipped += 1
            return
        report.folders_walked += 1
        local_dir = root.joinpath(*rel.split("/")) if rel else root
        local_files, local_dirs, local_errors, local_skipped = _list_local_children(
            local_dir, rel, exclude_globs=cfg.exclude_globs
        )
        report.errors.extend(local_errors)
        report.skipped += local_skipped
        try:
            listing = lister.list_children(rel)
        except Exception as exc:  # noqa: BLE001 — per-folder; keep walking
            report.errors.append(f"{rel or '.'}:{exc.__class__.__name__}:{exc}")
            listing = FolderListing(missing=True)
        remote_files, remote_dirs, remote_skipped = _remote_maps(
            listing, exclude_globs=cfg.exclude_globs
        )
        report.skipped += remote_skipped

        report.local_files += len(local_files)
        report.server_files += len(remote_files)

        for key, local in local_files.items():
            remote = remote_files.pop(key, None)
            if remote is None:
                unmatched_local.append(local)
                continue
            if compare_hashes:
                local_sha = None
                try:
                    local_sha = hasher(local_dir / local.name)
                except OSError as exc:
                    report.errors.append(f"{local.path}:hash:{exc.__class__.__name__}")
                server_sha = remote.sha256
                if local_sha and server_sha and local_sha.lower() != server_sha.lower():
                    report.hash_mismatches.append(
                        HashMismatch(
                            path=local.path,
                            local_sha256=local_sha,
                            server_sha256=server_sha,
                        ).to_dict()
                    )
        unmatched_server.extend(remote_files.values())

        dir_keys = set(local_dirs) | set(remote_dirs)
        for key in sorted(dir_keys):
            name = local_dirs.get(key) or (remote_dirs[key].name if key in remote_dirs else key)
            walk(child_rel(rel, name))

    for start in starts:
        if start and should_skip_relative(start, exclude_globs=cfg.exclude_globs, is_dir=True):
            report.skipped += 1
            continue
        walk(start)

    mismatches, local_only, server_only = _pair_path_mismatches(
        unmatched_local, unmatched_server
    )
    report.local_only = [row.to_dict() for row in local_only]
    report.server_only = [
        AuditEntry(
            path=item.posix,
            name=item.name,
            size=item.size,
            sha256=item.sha256,
        ).to_dict()
        for item in server_only
    ]
    report.path_mismatches = [row.to_dict() for row in mismatches]
    report.finished_at = _utc_now()
    path = report_path or default_report_path()
    report.write(path)
    return report
