from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.actions.drain import is_noise_file, is_secret_file
from harness.actions.inbox import InboxSorter
from harness.classify.router import ALLOWED_HOMES, correction_rule_rehome, match_correction_rules
from harness.config import HarnessConfig, load_correction_rules, load_taxonomy, match_exclude
from harness.graph.drive_client import GraphDriveClient
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move
from harness.ledger.documents import DocumentLedger, DocumentRecord
from harness.naming import (
    ORGANIZER_NAME_RE,
    held_reason_for_name,
    is_organizer_name,
    looks_like_bad_organizer_date,
    match_organizer_name,
    next_organizer_version,
    organizer_title_from_name,
    peel_rebuild_organizer_name,
    title_has_entity_and_topic,
)
from harness.stamp.harvest import HarvestStamp

CAPTURE_DIR_NAMES = {
    "_from_desktop",
    "_from_documents",
    "_from_downloads",
    "_from_mail",
}
# Client caches under 00-06 (e.g. 01/.../ClawdBot/Telegram Desktop).
# Skip at walk time so a multi-hour tree walk never starts.
JUNK_CACHE_DIR_NAMES = frozenset(
    {
        "telegram desktop",
        "clawdbot",
        "telegram",
    }
)
SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    ".trash",
    ".trashes",
    *JUNK_CACHE_DIR_NAMES,
}
HELPER_FILE_NAMES = {"_redirect_state.json"}


def homes_for_relabel(only: list[str] | None = None) -> list[str]:
    homes = sorted(ALLOWED_HOMES)
    default = [h for h in homes if h != "00_Inbox"] + [h for h in homes if h == "00_Inbox"]
    if not only:
        return default
    wanted: list[str] = []
    for item in only:
        raw = str(item).replace("\\", "/").strip("/")
        if not raw or raw not in ALLOWED_HOMES:
            raise ValueError(f"unknown relabel home: {item}")
        if raw not in wanted:
            wanted.append(raw)
    return [h for h in default if h in wanted]


def _homes_for_relabel(only: list[str] | None = None) -> list[str]:
    return homes_for_relabel(only)


def walk_files_tolerant(folder: Path) -> Iterator[Path]:
    """Walk files and skip directories OneDrive unlinks mid-scan (WinError 3)."""
    stack = [folder]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                lowered = entry.name.lower()
                if lowered in JUNK_CACHE_DIR_NAMES:
                    continue
                if lowered in SKIP_DIR_NAMES or entry.name in CAPTURE_DIR_NAMES:
                    continue
                stack.append(Path(entry.path))
            elif is_file:
                yield Path(entry.path)


def _junk_reason_for_path(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if "telegram desktop" in parts or "telegram" in parts:
        return "skip_telegram"
    if "clawdbot" in parts:
        return "skip_clawdbot"
    return "skip_telegram"


def _tally_junk_files(folder: Path, reasons: dict[str, int]) -> None:
    stack = [folder]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    key = _junk_reason_for_path(Path(entry.path))
                    reasons[key] = reasons.get(key, 0) + 1
            except OSError:
                continue


def tally_junk_skips(folder: Path, reasons: dict[str, int]) -> None:
    stack = [folder]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            lowered = entry.name.lower()
            if lowered in JUNK_CACHE_DIR_NAMES:
                _tally_junk_files(Path(entry.path), reasons)
                continue
            if lowered in SKIP_DIR_NAMES or entry.name in CAPTURE_DIR_NAMES:
                continue
            stack.append(Path(entry.path))


def iter_relabel_files(
    root: Path,
    exclude_globs: list[str],
    *,
    only: list[str] | None = None,
    reasons: dict[str, int] | None = None,
) -> list[Path]:
    files: list[Path] = []
    for home in _homes_for_relabel(only):
        folder = root / home
        if not folder.is_dir():
            continue
        if reasons is not None:
            tally_junk_skips(folder, reasons)
        for src in walk_files_tolerant(folder):
            try:
                if not src.is_file():
                    continue
                if src.name.lower() in HELPER_FILE_NAMES or is_noise_file(src):
                    continue
                if is_secret_file(src):
                    if reasons is not None:
                        reasons["skip_secret"] = reasons.get("skip_secret", 0) + 1
                    continue
                if any(part.lower() in SKIP_DIR_NAMES for part in src.parts):
                    continue
                if any(part in CAPTURE_DIR_NAMES for part in src.parts):
                    continue
                if match_exclude(src, exclude_globs):
                    continue
                files.append(src)
            except OSError:
                continue
    return files


def prioritize_relabel_sources(
    sources: list[Path],
    *,
    root: Path,
    rules: list[dict[str, Any]],
    ledger: DocumentLedger,
) -> list[Path]:
    """Law failures first so a proof --limit hits stacked leftovers, not already-law names.

    Organizer-law names whose peeled title is missing an entity or a topic are
    re-picked after stacked leftovers. A single generic word or a topic-only
    title is a miss; already-law names with Entity Topic stay on the skip/fill
    path.
    """
    broken: list[Path] = []
    weak_title: list[Path] = []
    rehome: list[Path] = []
    ledger_fill: list[Path] = []
    for src in sources:
        if not is_organizer_name(src.name):
            broken.append(src)
            continue
        if not title_has_entity_and_topic(organizer_title_from_name(src.name)):
            weak_title.append(src)
            continue
        if correction_rule_rehome(src, root=root, rules=rules) is not None:
            rehome.append(src)
            continue
        try:
            digest = content_hash(src)
        except OSError:
            continue
        if ledger.get(digest) is None:
            ledger_fill.append(src)
    return broken + weak_title + rehome + ledger_fill


def _commit_relabel(
    src: Path,
    *,
    dest_dir: Path,
    candidate: str,
    root: Path,
    run_id: str,
    journal: ActionJournal,
    ledger: DocumentLedger,
    type_by_prefix: dict[str, str],
    stamper: HarvestStamp,
    source: str,
    prefix: str,
    title: str,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in dest_dir.iterdir()} if dest_dir.exists() else set()
    name = next_organizer_version(existing, candidate)
    dest = dest_dir / name
    while dest.exists() and dest.resolve() != src.resolve():
        existing.add(dest.name)
        name = next_organizer_version(existing, candidate)
        dest = dest_dir / name
    item_id = None
    previous_path = str(src)
    if stamper.graph is not None:
        getter = getattr(stamper.graph, "get_item_by_path", None)
        if getter is not None:
            try:
                item = getter(str(src))
            except Exception:
                item = None
            if isinstance(item, dict):
                item_id = str(item.get("listItemId") or item.get("id") or "") or None
    digest = content_hash(src)
    if dest.resolve() != src.resolve():
        apply_move(src, dest)
        action = "move"
    else:
        action = "relabel"
    parsed = ORGANIZER_NAME_RE.match(dest.name)
    version = int(parsed.group("ver")) if parsed else 1
    doc_date = parsed.group("date") if parsed else ""
    try:
        home = dest.relative_to(root).parts[0]
    except ValueError:
        home = dest_dir.parts[0] if dest_dir.parts else "00_Inbox"
    journal.record(
        run_id,
        action,
        {
            "from": str(src),
            "to": str(dest),
            "sha256": digest,
            "classification": source,
            "prefix": prefix,
            "title": title,
            "doc_date": doc_date,
            "version": version,
        },
    )
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title=title,
            prefix=prefix,
            doc_type=type_by_prefix.get(prefix, prefix),
            doc_date=doc_date,
            version=version,
            home=home,
            current_path=str(dest),
            source=source,
        )
    )
    stamper.apply(
        dest,
        run_id=run_id,
        prefix=prefix,
        home=home,
        title=title,
        item_id=item_id,
        previous_path=previous_path,
    )
    return dest


@dataclass
class RelabelReport:
    run_id: str
    started_at: str
    finished_at: str
    scanned: int = 0
    renamed: int = 0
    peeled: int = 0
    ledger_only: int = 0
    held: int = 0
    skipped: int = 0
    errors: int = 0
    homes: list[str] = field(default_factory=list)
    completed_homes: list[str] = field(default_factory=list)
    held_reasons: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _bump_reason(report: RelabelReport, reason: str) -> None:
    if not reason:
        return
    report.held_reasons[reason] = report.held_reasons.get(reason, 0) + 1


def _home_of(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).parts[0]
    except ValueError:
        return ""


def run_relabel(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    llm_caller: Callable[..., str] | None = None,
    limit: int | None = None,
    graph: GraphDriveClient | None = None,
    only: list[str] | None = None,
) -> RelabelReport:
    started = datetime.now(timezone.utc).isoformat()
    run_id = journal.start_run(note="relabel")
    root = cfg.sync_root
    type_by_prefix = load_taxonomy(cfg.resolve_path(cfg.taxonomy_path))
    ledger = DocumentLedger(Path(journal.path))
    rules = load_correction_rules(cfg.resolve_path(cfg.correction_rules_path))
    report = RelabelReport(run_id=run_id, started_at=started, finished_at="")
    stamper = HarvestStamp(
        journal=journal,
        graph=graph,
        rules=rules,
        ledger=ledger,
        exclude_globs=cfg.exclude_globs,
    )
    if graph is None:
        report.notes.append("graph_offline")
    try:
        homes = homes_for_relabel(only)
    except ValueError as exc:
        report.errors += 1
        report.notes.append(str(exc))
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.write(report_path)
        return report
    report.homes = list(homes)
    if only:
        report.notes.append("only=" + ",".join(homes))
    from harness.jobs.home_lock import HomeLockSet, live_locks, lock_dir_for_journal

    lock_dir = lock_dir_for_journal(Path(journal.path))
    harvest_busy = live_locks(lock_dir, job="harvest")
    blocked = [h for h in homes if h in harvest_busy]
    if blocked:
        report.notes.append("harvest_lock:" + ",".join(blocked))
        homes = [h for h in homes if h not in blocked]
        report.homes = list(homes)
        if not homes:
            report.finished_at = datetime.now(timezone.utc).isoformat()
            report.write(report_path)
            return report
    locks = HomeLockSet(lock_dir, homes, job="relabel", pid=os.getpid())
    locks.acquire()
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=rules,
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
        stamper=stamper,
    )
    try:
        report.notes.append("peel_first=1")
        if limit is not None:
            report.notes.append(f"limit={limit}")
        budget = limit
        for home in homes:
            try:
                sources = iter_relabel_files(
                    root, cfg.exclude_globs, only=[home], reasons=report.held_reasons
                )
            except Exception as exc:
                report.notes.append(repr(exc))
                report.errors += 1
                report.finished_at = datetime.now(timezone.utc).isoformat()
                report.write(report_path)
                raise
            sources = prioritize_relabel_sources(
                sources, root=root, rules=rules, ledger=ledger
            )
            exhausted = False
            for src in sources:
                if budget is not None and budget <= 0:
                    exhausted = True
                    break
                report.scanned += 1
                if budget is not None:
                    budget -= 1
                _relabel_one_file(
                    src,
                    report=report,
                    root=root,
                    run_id=run_id,
                    journal=journal,
                    ledger=ledger,
                    type_by_prefix=type_by_prefix,
                    stamper=stamper,
                    sorter=sorter,
                    rules=rules,
                )
            if not exhausted:
                report.completed_homes.append(home)
                report.write(report_path)
            if exhausted:
                break
    finally:
        locks.release()
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report


def _relabel_one_file(
    src: Path,
    *,
    report: RelabelReport,
    root: Path,
    run_id: str,
    journal: ActionJournal,
    ledger: DocumentLedger,
    type_by_prefix: dict[str, str],
    stamper: HarvestStamp,
    sorter: InboxSorter,
    rules: list[dict[str, Any]],
) -> None:
    try:
        if looks_like_bad_organizer_date(src.name):
            _bump_reason(report, "skip_bad_date")
            report.skipped += 1
            return
        if not is_organizer_name(src.name):
            hit = match_correction_rules(src.name, rules)
            prefix_override = None
            if hit and hit.get("prefix"):
                prefix_override = str(hit.get("prefix"))
            rebuilt = peel_rebuild_organizer_name(src.name, prefix=prefix_override)
            if rebuilt is not None and title_has_entity_and_topic(
                organizer_title_from_name(rebuilt)
            ):
                rehome = correction_rule_rehome(src, root=root, rules=rules)
                dest_dir = (
                    root / str(rehome["target_folder"]).replace("\\", "/")
                    if rehome is not None
                    else src.parent
                )
                parsed = ORGANIZER_NAME_RE.match(rebuilt)
                assert parsed is not None
                dest = _commit_relabel(
                    src,
                    dest_dir=dest_dir,
                    candidate=rebuilt,
                    root=root,
                    run_id=run_id,
                    journal=journal,
                    ledger=ledger,
                    type_by_prefix=type_by_prefix,
                    stamper=stamper,
                    source="organizer_peel",
                    prefix=parsed.group("prefix"),
                    title=parsed.group("title"),
                )
                report.peeled += 1
                if dest.resolve() != src.resolve():
                    report.renamed += 1
                else:
                    report.ledger_only += 1
                return
        weak_title = is_organizer_name(src.name) and not title_has_entity_and_topic(
            organizer_title_from_name(src.name)
        )
        if (
            is_organizer_name(src.name)
            and not weak_title
            and correction_rule_rehome(src, root=root, rules=sorter.rules) is None
        ):
            if ledger.get(content_hash(src)) is not None:
                report.skipped += 1
                return
            parsed = match_organizer_name(src.name)
            digest = content_hash(src)
            home = _home_of(src, root) or "00_Inbox"
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
            stamper.apply(
                src,
                run_id=run_id,
                prefix=parsed.group("prefix"),
                home=home,
                title=parsed.group("title"),
            )
            report.ledger_only += 1
            return
        result = sorter.process_file(
            src, run_id=run_id, ignore_manifest=True, keep_folder=True
        )
        if result.status == "held":
            report.held += 1
            reason = result.detail or held_reason_for_name(src.name)
            _bump_reason(report, reason)
            journal.record(
                run_id,
                "hold",
                {"from": str(src), "reason": reason},
            )
        elif result.status == "moved":
            dest = result.dest
            unsorted = dest is not None and "00_Inbox/_Unsorted_Imports" in dest.as_posix()
            if unsorted:
                report.held += 1
                reason = result.detail or held_reason_for_name(src.name)
                _bump_reason(report, reason)
                journal.record(
                    run_id,
                    "hold",
                    {
                        "from": str(src),
                        "to": str(dest),
                        "reason": reason,
                    },
                )
            elif dest is not None and dest.resolve() != src.resolve():
                report.renamed += 1
            else:
                report.ledger_only += 1
        else:
            report.skipped += 1
    except Exception as exc:
        report.errors += 1
        journal.record(
            run_id,
            "error",
            {
                "from": str(src),
                "error": exc.__class__.__name__,
                "detail": str(exc)[:500],
            },
        )
        if len(report.notes) < 20:
            report.notes.append(f"{src.name}:{exc.__class__.__name__}")
