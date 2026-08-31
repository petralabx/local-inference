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


# Month 01–12 and day 01–31 only. Calendar validity is checked separately
# so 2022-02-30 is not law-shaped and never reaches date.fromisoformat.
ORGANIZER_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))_"
    r"(?P<prefix>[A-Z0-9]+)_(?P<title>.+)_v(?P<ver>\d+)\.(?P<ext>[^.]+)$"
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


def _leading_prefix_token(text: str) -> str | None:
    match = _LEADING_PREFIX_RE.match(text)
    if not match:
        return None
    return match.group(0).rstrip("_")


def _remainder_is_stacked(remainder: str) -> bool:
    if not remainder:
        return False
    if _LEADING_DATE_RE.match(remainder):
        return True
    if _LEADING_FOLDER_RE.match(remainder):
        return True
    if _LEADING_NUMBERED_HOME_RE.match(remainder):
        return True
    token = _leading_prefix_token(remainder)
    return bool(token and token in known_organizer_prefixes())


def last_known_organizer_prefix(name: str) -> str | None:
    """Last taxonomy/correction-rule PREFIX glued into a stacked filename."""
    known = known_organizer_prefixes()
    found: str | None = None
    for match in re.finditer(r"(?:^|_)([A-Z][A-Z0-9]{1,7})_", name):
        token = match.group(1)
        if token in known:
            found = token
    return found


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
            token = _leading_prefix_token(nxt)
            if token is not None:
                remainder = nxt[len(token) + 1 :]
                # Known PREFIX is the law slot (INV_Project Brief). Unknown
                # tokens stay unless the remainder is still a stacked wrapper
                # (ABC_2026-08-17_INV_... or ABC_01_CLIENTS_PROJECTS_...).
                if token in known_organizer_prefixes() or _remainder_is_stacked(
                    remainder
                ):
                    nxt = remainder
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


def parse_organizer_date(token: str) -> date | None:
    """Real calendar date, or None. Never invent a substitute date."""
    try:
        return date.fromisoformat(token)
    except ValueError:
        return None


def looks_like_bad_organizer_date(name: str) -> bool:
    """Leading YYYY-MM-DD_ that is not a real calendar date (month 20, Feb 30)."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_", name)
    if match is None:
        return False
    return parse_organizer_date(match.group(1)) is None


def peel_rebuild_organizer_name(name: str, *, prefix: str | None = None) -> str | None:
    """Rebuild a law-shaped (possibly stacked) filename to a single-law name.

    Returns None when the name is not law-shaped, so callers can fall through
    to classify. Correction-rule prefix, when provided, wins over the token
    glued into the filename.
    """
    parsed = ORGANIZER_NAME_RE.match(name)
    if parsed is None:
        return None
    when = parse_organizer_date(parsed.group("date"))
    if when is None:
        return None
    parsed_prefix = parsed.group("prefix")
    if prefix is not None:
        raw_prefix = prefix
    elif parsed_prefix in known_organizer_prefixes():
        raw_prefix = parsed_prefix
    else:
        raw_prefix = last_known_organizer_prefix(name) or parsed_prefix
    # Peel the full filename so a folder token that spans the regex
    # prefix/title split (BUSINESS_OPS) is removed as one leftover.
    title = peel_organizer_title(name)
    if not title:
        title = peel_organizer_title(parsed.group("title")) or "Untitled"
    rebuilt = build_organizer_name(
        when=when,
        prefix=raw_prefix,
        title=title,
        version=int(parsed.group("ver")),
        ext=parsed.group("ext"),
    )
    if not is_organizer_name(rebuilt):
        return None
    return rebuilt


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
    if parse_organizer_date(parsed.group("date")) is None:
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


# Title slot is Entity then Topic (two human parts). Not a fifth filename field.
_GENERIC_TITLE_WORDS = frozenset({"untitled", "document", "scan", "file", "image"})
_TOPIC_PHRASES: tuple[str, ...] = (
    "notice of assessment",
    "employee contract",
    "cost analysis",
    "credit note",
    "packing list",
    "stability quote",
    "invoices",
    "invoice",
    "quotes",
    "quote",
    "receipts",
    "receipt",
    "contracts",
    "contract",
    "agreements",
    "agreement",
    "proposals",
    "proposal",
    "estimates",
    "estimate",
    "statements",
    "statement",
    "orders",
    "order",
    "ndas",
    "nda",
    "memos",
    "memo",
    "minutes",
    "agendas",
    "agenda",
    "reports",
    "report",
    "credit notes",
    "packing lists",
    "notices",
    "notice",
    "assessments",
    "assessment",
    "analysis",
    "stability",
)
_TOPIC_WORDS = frozenset(p for p in _TOPIC_PHRASES if " " not in p)
# Conservative document-kind tokens for Party / title splits. Not NLP.
_KIND_ALTERNATION = "|".join(
    re.escape(p) for p in sorted(_TOPIC_PHRASES, key=len, reverse=True)
)
PARTY_KIND_RE = re.compile(rf"\b({_KIND_ALTERNATION})\b", re.I)


def display_title_part(text: str) -> str:
    """Preserve mixed/acronym case; title-case a fully lower/upper phrase."""
    cleaned = re.sub(r"[\s_-]+", " ", text).strip(" -_,./")
    if not cleaned:
        return ""
    tokens = cleaned.split()
    if len(tokens) == 1 and tokens[0].isupper() and 2 <= len(tokens[0]) <= 4:
        return tokens[0]
    if cleaned.islower() or cleaned.isupper():
        return cleaned.title()
    return cleaned


def _title_tokens(text: str) -> list[str]:
    return [tok for tok in re.split(r"[\s_-]+", text.strip()) if tok]


def _all_generic_tokens(text: str) -> bool:
    tokens = _title_tokens(text)
    return bool(tokens) and all(tok.lower() in _GENERIC_TITLE_WORDS for tok in tokens)


def _topic_span(text: str) -> tuple[int, int] | None:
    low = text.lower()
    best: tuple[int, int] | None = None
    for phrase in sorted(_TOPIC_PHRASES, key=len, reverse=True):
        start = 0
        while True:
            idx = low.find(phrase, start)
            if idx < 0:
                break
            end = idx + len(phrase)
            left_ok = idx == 0 or not low[idx - 1].isalnum()
            right_ok = end == len(low) or not low[end].isalnum()
            if left_ok and right_ok:
                if best is None or idx < best[0] or (idx == best[0] and end > best[1]):
                    best = (idx, end)
                break
            start = idx + 1
    return best


def split_entity_topic(title: str) -> tuple[str, str]:
    """Split a peeled title into (entity, topic). Empty entity means unknown."""
    text = peel_organizer_title(title).strip()
    if not text:
        return "", ""
    spaced = re.sub(r"[\s_-]+", " ", text).strip()
    if not spaced or _all_generic_tokens(spaced):
        return "", ""
    span = _topic_span(spaced)
    if span is not None:
        start, _end = span
        entity = display_title_part(spaced[:start])
        topic = display_title_part(spaced[start:])
        if not entity or entity.lower() in _GENERIC_TITLE_WORDS:
            return "", topic
        return entity, topic
    tokens = _title_tokens(spaced)
    head = tokens[0].lower()
    if (
        len(tokens) >= 2
        and head not in _GENERIC_TITLE_WORDS
        and head not in _TOPIC_WORDS
    ):
        return display_title_part(tokens[0]), display_title_part(" ".join(tokens[1:]))
    return "", ""


def title_has_entity_and_topic(title: str) -> bool:
    """True when the title slot has a named entity and a topic (not topic-only)."""
    entity, topic = split_entity_topic(title)
    return bool(entity and topic)


def build_entity_topic_title(entity: str, topic: str) -> str:
    """Join Entity then Topic without duplicating a title that already has both."""
    entity_part = display_title_part(entity)
    topic_part = display_title_part(topic)
    if not entity_part or not topic_part:
        return ""
    if topic_part.lower().startswith(entity_part.lower()):
        return topic_part
    return f"{entity_part} {topic_part}"


def organizer_title_from_name(name: str) -> str:
    """Peeled title slot from a law filename, else the peeled stem."""
    parsed = ORGANIZER_NAME_RE.match(name)
    if parsed:
        return peel_organizer_title(parsed.group("title")) or ""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return peel_organizer_title(stem) or stem


def topic_from_blob(*parts: str) -> str:
    """First known topic phrase in filename/text. Empty when none is named."""
    blob = re.sub(r"[\s_-]+", " ", " ".join(p for p in parts if p)).strip()
    if not blob:
        return ""
    span = _topic_span(blob)
    if span is None:
        return ""
    return display_title_part(blob[span[0] : span[1]])
