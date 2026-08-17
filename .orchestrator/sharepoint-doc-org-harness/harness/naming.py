from __future__ import annotations

import re
from datetime import date


_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<prefix>[A-Za-z0-9]+)_(?P<desc>[A-Za-z0-9_-]+)_v(?P<ver>\d+)\.(?P<ext>[^.]+)$"
)


def is_compliant(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def build_name(
    *,
    when: date,
    prefix: str,
    description: str,
    version: int = 1,
    ext: str,
) -> str:
    prefix = prefix.upper().strip()
    desc = re.sub(r"[^A-Za-z0-9_-]+", "", description.replace(" ", ""))
    if not desc:
        desc = "Untitled"
    ext = ext.lower().lstrip(".")
    return f"{when.isoformat()}_{prefix}_{desc}_v{version:02d}.{ext}"


def build_readable_name(*, description: str, ext: str) -> str:
    """Human title plus extension. Date, type, and version live in the journal."""
    stem = re.sub(r"[\\/]+", " ", description).strip()
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r'[<>:"|?*]', "", stem)
    stem = stem.rstrip(" .")
    if not stem:
        stem = "Untitled"
    ext = ext.lower().lstrip(".")
    if not ext:
        return stem
    return f"{stem}.{ext}"


def is_readable(name: str) -> bool:
    if "/" in name or "\\" in name:
        return False
    if name.startswith("."):
        return False
    return bool(re.match(r".+\.[A-Za-z0-9]+$", name))


def next_free_name(existing: set[str], candidate: str) -> str:
    if candidate not in existing:
        return candidate
    stem, dot, ext = candidate.rpartition(".")
    if not dot:
        stem, ext = candidate, ""
    n = 2
    while True:
        nxt = f"{stem}-{n}.{ext}" if ext else f"{stem}-{n}"
        if nxt not in existing:
            return nxt
        n += 1


def next_version_name(existing: set[str], candidate: str) -> str:
    """Bump _vNN until candidate is free within existing basenames."""
    m = _NAME_RE.match(candidate)
    if not m:
        return candidate
    ver = int(m.group("ver"))
    while candidate in existing:
        ver += 1
        candidate = (
            f"{m.group('date')}_{m.group('prefix')}_{m.group('desc')}_v{ver:02d}.{m.group('ext')}"
        )
    return candidate
