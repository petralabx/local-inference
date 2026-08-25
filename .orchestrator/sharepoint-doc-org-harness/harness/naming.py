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


ORGANIZER_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<prefix>[A-Z0-9]+)_(?P<title>.+)_v(?P<ver>\d+)\.(?P<ext>[^.]+)$"
)

# Leading law date token: YYYY-MM-DD_
_LEADING_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")
# Date used as a law prefix anywhere in the captured title (underscore, not a date in words).
_TITLE_DATE_PREFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}_")
# Taxonomy-like PREFIX: A-Z0-9, 2–8 chars, must start with a letter (INV, GEN, …).
_LEADING_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{1,7}_")
# Numbered VincePersonal homes used as a PREFIX stand-in (01, 02, …).
# Kept off _TITLE_FOLDER_RE so mid-title "_01_" is not a false leftover.
_LEADING_NUMBERED_HOME_RE = re.compile(r"^(?:00|01|02|03|04|05|06)(?:_|$)")
# Trailing extra version from a stacked law name: _vNN or leftover space-vNN.
# Optional .ext so a full filename (not just a stem) can be peeled.
_TRAILING_VERSION_RE = re.compile(r"(?:_v\d+| v\d+)(?:\.[A-Za-z]{2,5})?$")
_TITLE_VERSION_RE = re.compile(r"_v\d+")
_TITLE_SPACE_VERSION_RE = re.compile(r" v\d+$")
_FILENAME_EXT_RE = re.compile(r"\.[A-Za-z]{2,5}$")
_DEFAULT_PREFIX = "GEN"
_KNOWN_PREFIXES: frozenset[str] | None = None

# Folder tokens as they appear when a path fragment is glued into the filename.
# Numbered homes first, then unnumbered aliases. Longest match wins.
_FOLDER_TOKENS = (
    "00_INBOX",
    "01_CLIENTS_PROJECTS",
    "02_BUSINESS_OPS",
    "03_MARKETING_CREATIVE",
    "04_ADMIN",
    "05_PERSONAL",
    "06_REFERENCE",
    "CLIENTS_PROJECTS",
    "BUSINESS_OPS",
    "MARKETING_CREATIVE",
    "INBOX",
    "ADMIN",
    "PERSONAL",
    "REFERENCE",
)
_FOLDER_ALTERNATION = "|".join(
    re.escape(tok) for tok in sorted(_FOLDER_TOKENS, key=len, reverse=True)
)
_LEADING_FOLDER_RE = re.compile(
    rf"^(?:{_FOLDER_ALTERNATION})(?:_|$)",
    re.IGNORECASE,
)
_TITLE_FOLDER_RE = re.compile(
    rf"(?:^|_)(?:{_FOLDER_ALTERNATION})(?:_|$)",
    re.IGNORECASE,
)


def known_organizer_prefixes() -> frozenset[str]:
    """Taxonomy prefixes plus any prefix a correction rule is allowed to emit."""
    global _KNOWN_PREFIXES
    if _KNOWN_PREFIXES is None:
        from harness.config import PACKAGE_ROOT, load_correction_rules, load_taxonomy

        prefixes = {
            str(key).upper().strip()
            for key in load_taxonomy(PACKAGE_ROOT / "config" / "taxonomy_prefixes.yaml")
            if str(key).strip()
        }
        for rule in load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json"):
            extra = str(rule.get("prefix") or "").upper().strip()
            if extra:
                prefixes.add(extra)
        prefixes.add(_DEFAULT_PREFIX)
        _KNOWN_PREFIXES = frozenset(prefixes)
    return _KNOWN_PREFIXES


def normalize_organizer_prefix(prefix: str) -> str:
    """Keep a taxonomy/correction-rule prefix; map folder and unknown tokens to GEN."""
    cleaned = prefix.upper().strip()
    if cleaned in known_organizer_prefixes():
        return cleaned
    return _DEFAULT_PREFIX


def readable_title_from_filename(name: str) -> str:
    """SharePoint Title: peeled readable title, never the full law filename."""
    parsed = ORGANIZER_NAME_RE.match(name)
    if parsed:
        title = peel_organizer_title(parsed.group("title"))
        if title:
            return title
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return peel_organizer_title(stem) or stem or "Untitled"


def _strip_known_leading_prefix(text: str) -> str:
    """Strip only taxonomy/correction-rule PREFIX tokens, not Q4_ / PO_ titles."""
    match = _LEADING_PREFIX_RE.match(text)
    if not match:
        return text
    token = match.group(0).rstrip("_")
    if token not in known_organizer_prefixes():
        return text
    return text[match.end() :]


def peel_organizer_title(title: str) -> str:
    """Strip stacked law wrappers, keeping the readable title (spaces preserved)."""
    text = title
    if _LEADING_DATE_RE.match(text) or _TRAILING_VERSION_RE.search(text):
        text = _FILENAME_EXT_RE.sub("", text)
    after_date = False
    for _ in range(32):
        nxt = text
        if _LEADING_DATE_RE.match(nxt):
            nxt = _LEADING_DATE_RE.sub("", nxt, count=1)
            after_date = True
        # Folder tokens before taxonomy PREFIX so BUSINESS_OPS / PERSONAL
        # are not split into a fake prefix plus an OPS_ leftover.
        folded = _LEADING_FOLDER_RE.sub("", nxt, count=1)
        if folded != nxt:
            nxt = folded
            after_date = False
        if after_date:
            stripped = _strip_known_leading_prefix(nxt)
            if stripped != nxt:
                nxt = stripped
                after_date = False
        numbered = _LEADING_NUMBERED_HOME_RE.sub("", nxt, count=1)
        if numbered != nxt:
            nxt = numbered
            after_date = False
        nxt = _TRAILING_VERSION_RE.sub("", nxt, count=1)
        if nxt == text:
            break
        text = nxt
    return text.strip(" _")


def peel_rebuild_organizer_name(name: str, *, prefix: str | None = None) -> str | None:
    """Rebuild a law-shaped (possibly stacked) filename to a single-law name.

    Returns None when the name is not law-shaped, so callers can fall through
    to classify. Correction-rule prefix, when provided, wins over the token
    glued into the filename.
    """
    parsed = ORGANIZER_NAME_RE.match(name)
    if parsed is None:
        return None
    when = date.fromisoformat(parsed.group("date"))
    raw_prefix = prefix if prefix is not None else parsed.group("prefix")
    # Peel the full filename so a folder token that spans the regex
    # prefix/title split (BUSINESS_OPS) is removed as one leftover.
    title = peel_organizer_title(name)
    if not title:
        title = peel_organizer_title(parsed.group("title")) or "Untitled"
    return build_organizer_name(
        when=when,
        prefix=raw_prefix,
        title=title,
        version=int(parsed.group("ver")),
        ext=parsed.group("ext"),
    )


def build_organizer_name(
    *,
    when: date,
    prefix: str,
    title: str,
    version: int = 1,
    ext: str,
) -> str:
    """Organizer law (ADR 0011/0024): date + prefix + readable title + version."""
    prefix = normalize_organizer_prefix(prefix)
    stem = re.sub(r"[\\/<>:\"|?*]+", " ", title).strip()
    stem = re.sub(r"\s+", " ", stem)
    stem = stem.rstrip(" .")
    stem = peel_organizer_title(stem)
    stem = re.sub(r"\s+", " ", stem).strip(" _")
    stem = stem.rstrip(" .")
    if not stem:
        stem = "Untitled"
    ext = ext.lower().lstrip(".")
    if not ext:
        return f"{when.isoformat()}_{prefix}_{stem}_v{version:02d}"
    return f"{when.isoformat()}_{prefix}_{stem}_v{version:02d}.{ext}"


def is_organizer_name(name: str) -> bool:
    parsed = ORGANIZER_NAME_RE.match(name)
    if not parsed:
        return False
    if parsed.group("prefix") not in known_organizer_prefixes():
        return False
    title = parsed.group("title")
    if peel_organizer_title(title) != title:
        return False
    if _TITLE_DATE_PREFIX_RE.search(title):
        return False
    if _TITLE_VERSION_RE.search(title):
        return False
    if _TITLE_SPACE_VERSION_RE.search(title):
        return False
    if _TITLE_FOLDER_RE.search(title):
        return False
    return True


def next_organizer_version(existing: set[str], candidate: str) -> str:
    m = ORGANIZER_NAME_RE.match(candidate)
    if not m:
        return next_free_name(existing, candidate)
    if candidate not in existing:
        return candidate
    ver = int(m.group("ver"))
    while True:
        ver += 1
        nxt = (
            f"{m.group('date')}_{m.group('prefix')}_{m.group('title')}"
            f"_v{ver:02d}.{m.group('ext')}"
        )
        if nxt not in existing:
            return nxt


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
