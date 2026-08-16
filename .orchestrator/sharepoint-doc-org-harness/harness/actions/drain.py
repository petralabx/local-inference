from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from harness.identity import content_hash


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
