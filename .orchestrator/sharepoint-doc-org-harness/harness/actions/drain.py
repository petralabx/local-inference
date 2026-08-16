from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import yaml

from harness.config import match_exclude
from harness.identity import content_hash
from harness.naming import next_free_name

NOISE_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
SECRET_DIR_TOKENS = {".aws", ".ssh"}
SECRET_NAMES = {"credentials.json", "credentials", ".env", "id_rsa", "id_ed25519", "id_dsa"}
SECRET_SUFFIXES = {".pem", ".pfx", ".p12", ".key"}


def load_drain_map(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or {}
    if not isinstance(sources, dict) or not sources:
        raise ValueError(f"No sources in drain map: {path}")
    return {str(k): str(v) for k, v in sources.items()}


def resolve_home(source_rel: str, mapping: dict[str, str]) -> str:
    """Map a Petra-relative path to a VincePersonal home (first component)."""
    top = Path(source_rel.replace("\\", "/")).parts[0] if source_rel else ""
    if top in mapping:
        return mapping[top]
    return mapping.get(source_rel, "00_Inbox")


@dataclass
class DrainDecision:
    src: Path
    dest_home: str
    status: str  # plan | skip_duplicate
    sha256: str


def plan_unique_files(
    files: list[Path],
    *,
    source_root: Path,
    mapping: dict[str, str],
    known_hashes: set[str],
    hasher: Callable[[Path], str] = content_hash,
) -> list[DrainDecision]:
    """Classify unique files; journal-skip byte-identical copies."""
    seen = set(known_hashes)
    out: list[DrainDecision] = []
    for src in files:
        digest = hasher(src)
        try:
            rel = str(src.relative_to(source_root))
        except ValueError:
            rel = src.name
        home = resolve_home(rel, mapping)
        if digest in seen:
            out.append(DrainDecision(src, home, "skip_duplicate", digest))
            continue
        seen.add(digest)
        out.append(DrainDecision(src, home, "plan", digest))
    return out


def is_secret_file(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    if any(part in SECRET_DIR_TOKENS for part in parts):
        return True
    name = path.name.lower()
    if name in SECRET_NAMES or name.startswith(".env."):
        return True
    return path.suffix.lower() in SECRET_SUFFIXES


def dest_relative(source_rel: str, dest_home: str) -> Path:
    parts = Path(source_rel.replace("\\", "/")).parts
    remainder = parts[1:] if len(parts) > 1 else (Path(source_rel).name,)
    return Path(dest_home, *remainder)


def collect_source_files(
    source_root: Path,
    mapping: dict[str, str],
    *,
    only: Iterable[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> list[Path]:
    wanted = set(only) if only else set(mapping)
    files: list[Path] = []
    for top in wanted:
        folder = source_root / top
        if not folder.is_dir():
            continue
        for src in folder.rglob("*"):
            if not src.is_file():
                continue
            if exclude_globs and match_exclude(src, exclude_globs):
                continue
            files.append(src)
    return sorted(files)


def resolve_dest(src: Path, *, source_root: Path, dest_root: Path, dest_home: str) -> Path:
    try:
        rel = str(src.relative_to(source_root))
    except ValueError:
        rel = src.name
    dest = dest_root / dest_relative(rel, dest_home)
    if dest.exists():
        existing = {p.name for p in dest.parent.iterdir()} if dest.parent.exists() else set()
        dest = dest.with_name(next_free_name(existing, dest.name))
    return dest
