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
