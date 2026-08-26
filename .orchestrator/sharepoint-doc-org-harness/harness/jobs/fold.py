from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.actions.fold import (
    CollectedLeftover,
    FoldApplyBlocked,
    collect_tree_files,
    constrain_fold_destination,
    guard_apply,
    leftover_vs_taxonomy,
    list_leftover_trees,
    load_leftover_trees_config,
    taxonomy_homes,
)
from harness.classify.router import classify_with_order
from harness.config import HarnessConfig, load_correction_rules
from harness.extract.pipeline import extract_text
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move
from harness.naming import next_free_name

NEVER_HIDE = "never_hide_vince_personal"
NEVER_ARCHIVE = "never_archive_00_06"
FILE_CAP = 200


@dataclass
class FoldReport:
    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    apply: bool
    sync_root: str
    taxonomy_homes: list[str]
    leftover_vs_taxonomy: dict[str, list[str]]
    leftover_trees: list[dict[str, Any]] = field(default_factory=list)
    scanned: int = 0
    planned: int = 0
    moved: int = 0
    skipped_secret: int = 0
    skipped_code: int = 0
    skipped_noise: int = 0
    already_home: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _record_file(report: FoldReport, src: Path, dest: Path | None, status: str, source: str) -> None:
    if len(report.files) >= FILE_CAP:
        return
    report.files.append(
        {
            "src": str(src),
            "dest": str(dest) if dest else "",
            "status": status,
            "source": source,
        }
    )


def _resolve_dest(src: Path, dest_dir: Path, *, mkdir: bool) -> Path:
    if mkdir:
        dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest_dir.exists():
        return dest
    try:
        if dest.exists() and dest.resolve() != src.resolve():
            existing = {p.name for p in dest_dir.iterdir()}
            dest = dest_dir / next_free_name(existing, dest.name)
    except OSError:
        existing = {p.name for p in dest_dir.iterdir()} if dest_dir.exists() else set()
        dest = dest_dir / next_free_name(existing, dest.name)
    return dest


def run_fold(
    *,
    cfg: HarnessConfig,
    journal: ActionJournal,
    report_path: Path,
    apply: bool = False,
    only: list[str] | None = None,
    limit: int | None = None,
    llm_caller: Callable[..., str] | None = None,
    source_root: Path | None = None,
) -> FoldReport:
    """Plan leftover-tree fold into 00-06. Moves only when apply=True."""
    started = datetime.now(timezone.utc).isoformat()
    root = source_root or cfg.sync_root
    guard_apply(root, apply=apply)
    dry_run = not apply
    run_id = journal.start_run(note="fold" if apply else "fold-dry")
    spec = load_leftover_trees_config(cfg.resolve_path(cfg.leftover_trees_path))
    rules = load_correction_rules(cfg.resolve_path(cfg.correction_rules_path))
    report = FoldReport(
        run_id=run_id,
        started_at=started,
        finished_at="",
        dry_run=dry_run,
        apply=apply,
        sync_root=str(root),
        taxonomy_homes=taxonomy_homes(),
        leftover_vs_taxonomy=leftover_vs_taxonomy(
            root, nested=spec["nested"], known_roots=spec["known_roots"]
        ),
        notes=[
            NEVER_HIDE,
            NEVER_ARCHIVE,
            "fold_is_hygiene_after_harvest_stamp",
        ],
    )
    if dry_run:
        report.notes.append("dry_run")
        report.notes.append("apply=false; pass --apply to execute moves")

    trees = list_leftover_trees(
        root,
        nested=spec["nested"],
        known_roots=spec["known_roots"],
    )
    if only:
        wanted = {item.replace("\\", "/").strip("/") for item in only}
        trees = [tree for tree in trees if tree.rel in wanted]

    collected: list[CollectedLeftover] = [
        collect_tree_files(root, tree, exclude_globs=cfg.exclude_globs) for tree in trees
    ]
    for item in collected:
        report.skipped_secret += item.skips.secret
        report.skipped_code += item.skips.code
        report.skipped_noise += item.skips.noise

    planned_files: list[tuple[CollectedLeftover, Path]] = []
    for item in collected:
        for src in item.files:
            planned_files.append((item, src))
            report.scanned += 1
    if limit is not None:
        planned_files = planned_files[: max(0, limit)]
        report.notes.append(f"limit={limit}")

    dest_counts: dict[str, Counter[str]] = {item.tree.rel: Counter() for item in collected}

    for item, src in planned_files:
        try:
            extracted = extract_text(src)
            classification = classify_with_order(
                path=src,
                text=extracted.text,
                rules=rules,
                litellm_base_url=cfg.litellm.base_url,
                model=cfg.litellm.classify_model,
                forbid_host_substrings=cfg.litellm.forbid_host_substrings,
                llm_caller=llm_caller,
                readable_names=cfg.readable_names,
                organizer_names=cfg.organizer_names,
                fallback_model=cfg.litellm.fallback_model,
                allow_live_llm=False,
            )
            dest_folder = constrain_fold_destination(classification.target_folder, item.tree.rel)
            dest_dir = root / dest_folder
            dest = _resolve_dest(src, dest_dir, mkdir=apply)
            try:
                same = dest.exists() and dest.resolve() == src.resolve()
            except OSError:
                same = False
            dest_counts[item.tree.rel][dest_folder] += 1
            if same:
                report.already_home += 1
                _record_file(report, src, dest, "already_home", classification.source)
                continue
            report.planned += 1
            if dry_run:
                _record_file(report, src, dest, "plan", classification.source)
                continue
            digest = content_hash(src)
            apply_move(src, dest)
            journal.record(
                run_id,
                "move",
                {
                    "from": str(src),
                    "to": str(dest),
                    "sha256": digest,
                    "classification": classification.source,
                    "leftover_tree": item.tree.rel,
                },
            )
            report.moved += 1
            _record_file(report, src, dest, "moved", classification.source)
        except FoldApplyBlocked:
            raise
        except OSError as exc:
            report.errors += 1
            if len(report.notes) < 40:
                report.notes.append(f"{src}: {exc}")
            _record_file(report, src, None, "error", "")

    tree_rows: list[dict[str, Any]] = []
    for item in collected:
        tree_rows.append(
            {
                "rel": item.tree.rel,
                "kind": item.tree.kind,
                "exists": item.tree.exists,
                "file_count": len(item.files),
                "skipped_secret": item.skips.secret,
                "skipped_code": item.skips.code,
                "skipped_noise": item.skips.noise,
                "proposed_destinations": dict(sorted(dest_counts[item.tree.rel].items())),
            }
        )
    tree_rows.sort(key=lambda row: (-int(row["file_count"]), str(row["rel"])))
    report.leftover_trees = tree_rows
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.write(report_path)
    return report
