from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from harness.actions.drain import is_noise_file, is_secret_file
from harness.config import match_exclude
from harness.identity import content_hash

STATUS_CANDIDATE = "candidate-to-consume"
STATUS_SKIP_CODE = "skip-code"
STATUS_SKIP_SECRET = "skip-secret"
STATUS_ALREADY = "already-in-VincePersonal"

CODE_DIR_NAMES = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "agentic-swarm",
}

SECRET_DIR_NAMES = {".aws", ".ssh"}

# Loose leftover scripts and binaries are not Documents (ADR 0008).
CODE_FILE_SUFFIXES = {
    ".py",
    ".pyw",
    ".pyc",
    ".pyo",
    ".ipynb",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".ps1",
    ".psm1",
    ".psd1",
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".cmd",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".sql",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".msi",
    ".com",
}

CODE_BASENAMES = {
    "dockerfile",
    "makefile",
    "cmakelists.txt",
    "vagrantfile",
    "gemfile",
    "rakefile",
    "package.json",
    "package-lock.json",
    "composer.json",
    "go.mod",
    "cargo.toml",
}

DOCUMENT_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".docm",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".xlsb",
    ".ppt",
    ".pptx",
    ".pptm",
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".heic",
    ".heif",
    ".webp",
    ".tif",
    ".tiff",
    ".bmp",
    ".one",
    ".msg",
    ".eml",
    ".html",
    ".htm",
    ".pages",
    ".numbers",
    ".key",
    ".epub",
    ".vsd",
    ".vsdx",
    ".pub",
}

EXTRA_SECRET_NAMES = {
    ".npmrc",
    ".netrc",
    ".pypirc",
    ".pgpass",
    ".git-credentials",
    ".gitconfig",
    "nuget.config",
}

SECRET_NAME_FRAGMENTS = (
    "password",
    "passwd",
    "bitwarden",
    "lastpass",
    "1password",
    "keepass",
    "vault_export",
    "credential",
    "client_secret",
)


def _safe_resolve(path: Path) -> Path | None:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return None


def _paths_for_classify(path: Path) -> list[Path]:
    paths = [path]
    resolved = _safe_resolve(path)
    if resolved is not None and resolved != path:
        paths.append(resolved)
    return paths


def load_inventory_roots(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    roots = data.get("roots") or []
    if not isinstance(roots, list):
        raise ValueError(f"inventory roots file must have a roots list: {path}")
    return [str(item).strip() for item in roots if str(item).strip()]


def merge_roots(*groups: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        if not group:
            continue
        for raw in group:
            text = str(raw).strip()
            if not text:
                continue
            key = os.path.normcase(text.replace("\\", "/").rstrip("/"))
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def is_under(path: Path, root: Path) -> bool:
    """True when path is the root or a descendant. Resolves junctions/symlinks."""
    resolved = _safe_resolve(path) or path
    root_res = _safe_resolve(root) or root
    try:
        resolved.relative_to(root_res)
        return True
    except ValueError:
        pass
    left = os.path.normcase(str(resolved))
    right = os.path.normcase(str(root_res)).rstrip("\\/")
    if left == right:
        return True
    sep = "\\" if ("\\" in right or right[1:3] == ":\\") else os.sep
    prefix = right + ("" if right.endswith(("/" if sep == "/" else "\\")) else sep)
    # Use both separators so Windows-style roots still match on POSIX tests.
    return left.startswith(prefix) or left.startswith(right + "/") or left.startswith(right + "\\")


def path_has_token(path: Path, tokens: Iterable[str]) -> bool:
    parts = [part.lower() for part in path.parts]
    joined = "/".join(parts)
    for token in tokens:
        t = str(token).lower().replace("\\", "/").strip("/")
        if not t:
            continue
        if "/" in t:
            if t in joined:
                return True
            continue
        if t in parts:
            return True
        if t.startswith("agentic-swarm") and any(p.startswith("agentic-swarm") for p in parts):
            return True
    return False


def _dir_looks_like_code(path: Path, extra_tokens: Iterable[str]) -> bool:
    name = path.name.lower()
    if name in CODE_DIR_NAMES or name.startswith("agentic-swarm"):
        return True
    if path_has_token(path, extra_tokens):
        return True
    git_marker = path / ".git"
    try:
        return git_marker.exists()
    except OSError:
        return False


def is_code_dir(path: Path, extra_tokens: Iterable[str]) -> bool:
    return any(_dir_looks_like_code(item, extra_tokens) for item in _paths_for_classify(path))


def _looks_like_secret(path: Path) -> bool:
    if is_secret_file(path) or path_has_token(path, SECRET_DIR_NAMES):
        return True
    name = path.name.lower()
    if name in EXTRA_SECRET_NAMES:
        return True
    if any(fragment in name for fragment in SECRET_NAME_FRAGMENTS):
        return True
    if name.endswith("serviceaccount.json") or name.endswith("service_account.json"):
        return True
    return False


def _looks_like_code(path: Path, exclude_globs: list[str], extra_tokens: list[str]) -> bool:
    if match_exclude(path, exclude_globs) or path_has_token(path, extra_tokens):
        return True
    if any(part.lower() in CODE_DIR_NAMES or part.lower().startswith("agentic-swarm") for part in path.parts):
        return True
    if path.suffix.lower() in CODE_FILE_SUFFIXES:
        return True
    if path.name.lower() in CODE_BASENAMES:
        return True
    return False


def _is_document(path: Path) -> bool:
    return path.suffix.lower() in DOCUMENT_SUFFIXES


def classify_file(
    path: Path,
    *,
    sync_root: Path,
    exclude_globs: list[str],
    extra_tokens: list[str],
) -> str:
    views = _paths_for_classify(path)
    if any(_looks_like_secret(item) for item in views):
        return STATUS_SKIP_SECRET
    if any(_looks_like_code(item, exclude_globs, extra_tokens) for item in views):
        return STATUS_SKIP_CODE
    if not all(_is_document(item) for item in views):
        return STATUS_SKIP_CODE
    if is_under(path, sync_root):
        return STATUS_ALREADY
    return STATUS_CANDIDATE


@dataclass
class InventoryHit:
    path: Path
    status: str
    root: Path
    kind: str  # file | tree
    sha256: str = ""


def _dir_key(path: Path) -> str:
    resolved = _safe_resolve(path)
    return os.path.normcase(str(resolved if resolved is not None else path))


def _entry_kind(entry: os.DirEntry[str]) -> tuple[bool, bool]:
    try:
        is_dir = entry.is_dir(follow_symlinks=False)
        is_file = entry.is_file(follow_symlinks=False)
        if entry.is_symlink():
            resolved = _safe_resolve(Path(entry.path))
            if resolved is None:
                return False, False
            if resolved.is_dir():
                return True, False
            if resolved.is_file():
                return False, True
            return False, False
    except (OSError, RuntimeError):
        return False, False
    return is_dir, is_file


def walk_inventory_roots(
    roots: list[Path],
    *,
    sync_root: Path,
    exclude_globs: list[str],
    extra_tokens: list[str],
    limit: int | None = None,
) -> tuple[list[InventoryHit], list[str], int]:
    """Walk operator-supplied roots. Never copies. Returns hits, missing roots, noise skips."""
    hits: list[InventoryHit] = []
    missing: list[str] = []
    skipped_noise = 0
    classified_files = 0
    seen_dirs: set[str] = set()
    seen_files: set[str] = set()

    def over_limit() -> bool:
        return limit is not None and classified_files >= max(0, limit)

    for raw_root in roots:
        root = Path(raw_root)
        if not root.exists():
            missing.append(str(root))
            continue
        stack: list[tuple[Path, Path]] = []
        if root.is_file():
            if over_limit():
                break
            if is_noise_file(root):
                skipped_noise += 1
                continue
            key = _dir_key(root)
            if key in seen_files:
                continue
            seen_files.add(key)
            hits.append(
                InventoryHit(
                    path=root,
                    status=classify_file(
                        root,
                        sync_root=sync_root,
                        exclude_globs=exclude_globs,
                        extra_tokens=extra_tokens,
                    ),
                    root=root.parent,
                    kind="file",
                )
            )
            classified_files += 1
            continue
        if not root.is_dir():
            missing.append(str(root))
            continue
        if is_code_dir(root, extra_tokens):
            hits.append(
                InventoryHit(path=root, status=STATUS_SKIP_CODE, root=root, kind="tree")
            )
            continue
        key = _dir_key(root)
        if key in seen_dirs:
            continue
        stack.append((root, root))
        seen_dirs.add(key)
        while stack and not over_limit():
            current, scan_root = stack.pop()
            if current != scan_root and is_code_dir(current, extra_tokens):
                hits.append(
                    InventoryHit(path=current, status=STATUS_SKIP_CODE, root=scan_root, kind="tree")
                )
                continue
            try:
                with os.scandir(current) as it:
                    entries = list(it)
            except OSError:
                continue
            for entry in entries:
                if over_limit():
                    break
                is_dir, is_file = _entry_kind(entry)
                child = Path(entry.path)
                if is_dir:
                    if is_code_dir(child, extra_tokens):
                        hits.append(
                            InventoryHit(
                                path=child, status=STATUS_SKIP_CODE, root=scan_root, kind="tree"
                            )
                        )
                        continue
                    key = _dir_key(child)
                    if key in seen_dirs:
                        continue
                    seen_dirs.add(key)
                    stack.append((child, scan_root))
                    continue
                if not is_file:
                    continue
                if is_noise_file(child):
                    skipped_noise += 1
                    continue
                file_key = _dir_key(child)
                if file_key in seen_files:
                    continue
                seen_files.add(file_key)
                hits.append(
                    InventoryHit(
                        path=child,
                        status=classify_file(
                            child,
                            sync_root=sync_root,
                            exclude_globs=exclude_globs,
                            extra_tokens=extra_tokens,
                        ),
                        root=scan_root,
                        kind="file",
                    )
                )
                classified_files += 1

    for hit in hits:
        if hit.kind != "file" or hit.status != STATUS_CANDIDATE:
            continue
        try:
            hit.sha256 = content_hash(hit.path)
        except (OSError, RuntimeError):
            hit.sha256 = ""
    return hits, missing, skipped_noise
