from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from harness.actions.drain import is_noise_file, is_secret_file
from harness.classify.router import ALLOWED_HOMES, UNSORTED_FOLDER, constrain_target_folder
from harness.config import match_exclude

TAXONOMY_HOMES = frozenset(ALLOWED_HOMES)
LIVE_ROOT_MARKERS = ("Vince Personal - Documents", "Petra Hygienic Systems")
ARCHIVE_TOKENS = {"_archive", "09_archive"}
SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    ".trash",
    ".trashes",
}
ROOT_FILES_KEY = "_root"


class FoldApplyBlocked(RuntimeError):
    """Raised when --apply would target a live Vince Personal library off-box."""


@dataclass
class LeftoverTree:
    rel: str
    kind: str  # root | nested
    exists: bool
    path: Path


@dataclass
class FileSkipCounts:
    secret: int = 0
    code: int = 0
    noise: int = 0


@dataclass
class CollectedLeftover:
    tree: LeftoverTree
    files: list[Path] = field(default_factory=list)
    skips: FileSkipCounts = field(default_factory=FileSkipCounts)


def load_leftover_trees_config(path: Path) -> dict[str, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    nested = [str(x).replace("\\", "/").strip("/") for x in (data.get("nested") or [])]
    known_roots = [str(x).replace("\\", "/").strip("/") for x in (data.get("known_roots") or [])]
    if any(item in TAXONOMY_HOMES for item in nested):
        raise ValueError(f"leftover nested list must not include taxonomy homes: {path}")
    if any(item in TAXONOMY_HOMES for item in known_roots):
        raise ValueError(f"leftover known_roots must not include taxonomy homes: {path}")
    return {"nested": nested, "known_roots": known_roots}


def looks_like_live_vincepersonal(root: Path) -> bool:
    text = str(root).replace("\\", "/")
    return all(marker in text for marker in LIVE_ROOT_MARKERS)


def guard_apply(root: Path, *, apply: bool) -> None:
    """Cloud VMs must not fold a real Vince Personal library."""
    if not apply:
        return
    if looks_like_live_vincepersonal(root) and sys.platform != "win32":
        raise FoldApplyBlocked(
            "refusing --apply against Vince Personal from a non-Windows host "
            "(Cloud VM must not fold a real library)"
        )


def is_archive_rel(folder: str) -> bool:
    parts = [p.lower() for p in folder.replace("\\", "/").split("/") if p]
    return any(part in ARCHIVE_TOKENS or part == "archive" for part in parts)


def constrain_fold_destination(folder: str, leftover_rel: str) -> str:
    """Keep destinations inside 00-06. Never archive. Never stay in the leftover pile."""
    cleaned = constrain_target_folder(folder)
    if is_archive_rel(cleaned):
        return UNSORTED_FOLDER
    leftover_norm = leftover_rel.replace("\\", "/").strip("/")
    cleaned_norm = cleaned.replace("\\", "/").strip("/")
    if leftover_norm and leftover_norm != ROOT_FILES_KEY:
        if cleaned_norm == leftover_norm or cleaned_norm.startswith(leftover_norm + "/"):
            return UNSORTED_FOLDER
    top = cleaned_norm.split("/", 1)[0]
    if top not in TAXONOMY_HOMES:
        return UNSORTED_FOLDER
    return cleaned_norm


def is_code_path(path: Path, exclude_globs: list[str], *, root: Path | None = None) -> bool:
    if match_exclude(path, exclude_globs):
        return True
    stop = root.resolve() if root is not None else None
    for parent in path.parents:
        if parent.name.lower() in {".git", "node_modules", ".venv", "agentic-swarm"}:
            return True
        try:
            if parent.name != ".git" and parent.is_dir() and (parent / ".git").is_dir():
                return True
        except OSError:
            continue
        if stop is not None:
            try:
                if parent.resolve() == stop:
                    break
            except OSError:
                break
    return False


def _skip_dir(name: str) -> bool:
    low = name.lower()
    if low in SKIP_DIR_NAMES:
        return True
    if name.startswith("_") or name.startswith("."):
        return True
    return False


def list_leftover_trees(
    root: Path,
    *,
    nested: list[str],
    known_roots: list[str],
) -> list[LeftoverTree]:
    """Leftover piles vs taxonomy 00-06. Canonical homes are never leftover trees."""
    seen: set[str] = set()
    trees: list[LeftoverTree] = []

    def _add(rel: str, kind: str, path: Path, exists: bool) -> None:
        key = rel.replace("\\", "/").strip("/") or ROOT_FILES_KEY
        if key in seen or key in TAXONOMY_HOMES:
            return
        seen.add(key)
        trees.append(LeftoverTree(rel=key, kind=kind, exists=exists, path=path))

    if root.is_dir():
        try:
            children = list(root.iterdir())
        except OSError:
            children = []
        for child in children:
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if not is_dir:
                continue
            if _skip_dir(child.name) or child.name in TAXONOMY_HOMES:
                continue
            _add(child.name, "root", child, True)
        loose = False
        for child in children:
            try:
                if child.is_file() and not is_noise_file(child):
                    loose = True
                    break
            except OSError:
                continue
        if loose:
            _add(ROOT_FILES_KEY, "root", root, True)

    for name in known_roots:
        path = root / name
        exists = path.is_dir()
        _add(name, "root", path, exists)

    for rel in nested:
        path = root / rel
        _add(rel, "nested", path, path.is_dir())

    return trees


def collect_tree_files(
    root: Path,
    tree: LeftoverTree,
    *,
    exclude_globs: list[str],
) -> CollectedLeftover:
    out = CollectedLeftover(tree=tree)
    if not tree.exists:
        return out
    if tree.rel == ROOT_FILES_KEY:
        try:
            candidates = [p for p in tree.path.iterdir() if p.is_file()]
        except OSError:
            return out
    else:
        candidates = []
        try:
            for src in tree.path.rglob("*"):
                try:
                    if src.is_file():
                        candidates.append(src)
                except OSError:
                    continue
        except OSError:
            return out

    for src in sorted(candidates, key=lambda p: str(p).lower()):
        if is_noise_file(src):
            out.skips.noise += 1
            continue
        if is_secret_file(src):
            out.skips.secret += 1
            continue
        if is_code_path(src, exclude_globs, root=root):
            out.skips.code += 1
            continue
        out.files.append(src)
    return out


def leftover_vs_taxonomy(root: Path, *, nested: list[str], known_roots: list[str]) -> dict[str, list[str]]:
    trees = list_leftover_trees(root, nested=nested, known_roots=known_roots)
    return {
        "taxonomy": taxonomy_homes(),
        "leftover_roots": [t.rel for t in trees if t.kind == "root"],
        "nested_leftovers": [t.rel for t in trees if t.kind == "nested"],
    }


def taxonomy_homes() -> list[str]:
    return sorted(TAXONOMY_HOMES)
