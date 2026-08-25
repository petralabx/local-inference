from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.actions.drain import is_secret_file
from harness.classify.router import match_correction_rules
from harness.config import match_exclude
from harness.graph.drive_client import (
    DOCUMENT_CONTENT_TYPE,
    GraphDriveClient,
    GraphOfflineError,
    ORGANIZER_COLUMNS,
)
from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger
from harness.naming import (
    ORGANIZER_NAME_RE,
    normalize_organizer_prefix,
    peel_organizer_title,
    readable_title_from_filename,
)
from harness.stamp.embed import write_embedded_properties

# Conservative document-kind tokens for Party fallback. Not NLP: split on these
# words and keep the short leading phrase, or leave Party empty.
_KIND_RE = (
    r"quotes?|invoices?|receipts?|contracts?|agreements?|proposals?|"
    r"estimates?|statements?|orders?|ndas?|memos?|minutes|"
    r"agendas?|sops?|reports?|pos?|credit notes?|packing lists?"
)
_PARTY_KIND_RE = re.compile(rf"\b({_KIND_RE})\b", re.I)


def party_for_document(
    *,
    filename: str,
    title: str,
    rules: list[dict[str, Any]],
) -> str:
    """Party from the matching correction-rule keyword, else a conservative peel.

    Empty Party is allowed. Does not invent NLP.
    """
    blob = f"{filename} {title}"
    hit = match_correction_rules(blob, rules) or match_correction_rules(filename, rules)
    if hit:
        keywords = sorted((str(k) for k in (hit.get("keywords") or [])), key=len, reverse=True)
        low = blob.lower()
        for kw in keywords:
            needle = kw.lower()
            idx = low.find(needle)
            if idx >= 0:
                return blob[idx : idx + len(kw)].strip() or kw.title()
        if keywords:
            return keywords[0].title()
    return conservative_party_from_title(title)


def conservative_party_from_title(title: str) -> str:
    text = peel_organizer_title(title).strip()
    if not text:
        return ""
    match = _PARTY_KIND_RE.search(text)
    if not match or match.start() == 0:
        return ""
    head = text[: match.start()].strip(" -_,./")
    words = [w for w in head.split() if w]
    if not words or len(words) > 6:
        return ""
    return " ".join(words)


def keyword_list(party: str, prefix: str) -> str:
    parts = [p for p in (party.strip(), prefix.strip()) if p]
    return "; ".join(parts)


@dataclass
class StampResult:
    path: Path
    title: str
    party: str
    prefix: str
    home: str
    columns_written: bool
    columns_skipped: bool
    embedded: dict[str, Any]
    sha256_before: str
    sha256_after: str
    skipped: str = ""


class HarvestStamp:
    """Project ledger identity onto SharePoint Title + Party/Prefix/Home + embeds."""

    def __init__(
        self,
        *,
        journal: ActionJournal,
        graph: GraphDriveClient | None = None,
        rules: list[dict[str, Any]] | None = None,
        ledger: DocumentLedger | None = None,
        exclude_globs: list[str] | None = None,
    ) -> None:
        self.journal = journal
        self.graph = graph
        self.rules = rules or []
        self.ledger = ledger
        self.exclude_globs = exclude_globs or []
        self._columns_ensured = False

    def ensure_site_columns(self) -> bool:
        """Create indexed SITE columns and add them to the default Document CT."""
        if self.graph is None:
            return False
        if self._columns_ensured:
            return True
        try:
            for col in ORGANIZER_COLUMNS:
                self.graph.ensure_site_column(
                    name=col.name,
                    display_name=col.display_name,
                    indexed=True,
                )
                self.graph.add_column_to_document_content_type(col.name)
            self._columns_ensured = True
            return True
        except GraphOfflineError:
            return False
        except Exception:
            return False

    def apply(
        self,
        path: Path,
        *,
        run_id: str,
        prefix: str,
        home: str,
        title: str | None = None,
        sha256: str | None = None,
        party: str | None = None,
    ) -> StampResult:
        if not path.is_file():
            return StampResult(
                path=path,
                title="",
                party="",
                prefix=prefix,
                home=home,
                columns_written=False,
                columns_skipped=True,
                embedded={"written": False, "reason": "missing"},
                sha256_before="",
                sha256_after="",
                skipped="not a file",
            )
        if is_secret_file(path):
            return self._skip(path, prefix, home, "secret", run_id=run_id)
        if match_exclude(path, self.exclude_globs):
            return self._skip(path, prefix, home, "code_or_exclude", run_id=run_id)

        readable = title or readable_title_from_filename(path.name)
        readable = peel_organizer_title(readable) or readable
        prefix = normalize_organizer_prefix(prefix)
        party_value = party if party is not None else party_for_document(
            filename=path.name, title=readable, rules=self.rules
        )
        before = sha256 or content_hash(path)
        embedded = write_embedded_properties(
            path,
            title=readable,
            subject=readable,
            keywords=keyword_list(party_value, prefix),
        )
        after = content_hash(path) if path.is_file() else before
        if self.ledger is not None and after != before:
            self.ledger.rekey(before, after)

        columns_written = False
        columns_skipped = True
        if self.graph is not None:
            ensured = self.ensure_site_columns()
            if ensured:
                fields = {
                    "Title": readable,
                    "OrganizerParty": party_value,
                    "OrganizerPrefix": prefix,
                    "OrganizerHome": home,
                }
                try:
                    self.graph.patch_list_item_fields(str(path), fields)
                    columns_written = True
                    columns_skipped = False
                except GraphOfflineError:
                    columns_written = False
                    columns_skipped = True
                except Exception:
                    columns_written = False
                    columns_skipped = True

        result = StampResult(
            path=path,
            title=readable,
            party=party_value,
            prefix=prefix,
            home=home,
            columns_written=columns_written,
            columns_skipped=columns_skipped,
            embedded=embedded,
            sha256_before=before,
            sha256_after=after,
        )
        self.journal.record(
            run_id,
            "stamp",
            {
                "path": str(path),
                "title": readable,
                "party": party_value,
                "prefix": prefix,
                "home": home,
                "columns_written": columns_written,
                "columns_skipped": columns_skipped,
                "embedded": embedded,
                "sha256_before": before,
                "sha256_after": after,
                "content_type": DOCUMENT_CONTENT_TYPE,
            },
        )
        return result

    def _skip(
        self,
        path: Path,
        prefix: str,
        home: str,
        reason: str,
        *,
        run_id: str,
    ) -> StampResult:
        result = StampResult(
            path=path,
            title="",
            party="",
            prefix=prefix,
            home=home,
            columns_written=False,
            columns_skipped=True,
            embedded={"written": False, "reason": reason},
            sha256_before="",
            sha256_after="",
            skipped=reason,
        )
        self.journal.record(
            run_id,
            "stamp",
            {
                "path": str(path),
                "skipped": reason,
                "columns_skipped": True,
            },
        )
        return result


def identity_from_path(
    path: Path,
    *,
    root: Path,
    ledger: DocumentLedger | None,
) -> tuple[str, str, str]:
    """Title, prefix, home from ledger or a peeled law name."""
    digest = content_hash(path)
    rec = ledger.get(digest) if ledger is not None else None
    parsed = ORGANIZER_NAME_RE.match(path.name)
    if rec is not None:
        prefix = rec.prefix
        home = rec.home
        title = peel_organizer_title(rec.title) or rec.title or readable_title_from_filename(
            path.name
        )
        if ORGANIZER_NAME_RE.match(title) or ORGANIZER_NAME_RE.match(rec.title or ""):
            title = readable_title_from_filename(rec.title or path.name)
    else:
        title = readable_title_from_filename(path.name)
        prefix = parsed.group("prefix") if parsed else "GEN"
        try:
            home = path.relative_to(root).parts[0]
        except ValueError:
            home = "00_Inbox"
    return title, normalize_organizer_prefix(prefix), home
