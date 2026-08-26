from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

# Locked Vince Personal site-column contract. Internal names stay stable so
# crawled properties (ows_OrganizerParty / Prefix / Home) do not churn.
# Display names are Party, Prefix, Home. Indexed so list views survive 5k.


@dataclass(frozen=True)
class OrganizerColumn:
    name: str
    display_name: str
    crawled_property: str
    refinable_alias: str
    refinable_string: str


ORGANIZER_COLUMNS: tuple[OrganizerColumn, ...] = (
    OrganizerColumn(
        name="OrganizerParty",
        display_name="Party",
        crawled_property="ows_OrganizerParty",
        refinable_alias="Party",
        refinable_string="RefinableString00",
    ),
    OrganizerColumn(
        name="OrganizerPrefix",
        display_name="Prefix",
        crawled_property="ows_OrganizerPrefix",
        refinable_alias="Prefix",
        refinable_string="RefinableString01",
    ),
    OrganizerColumn(
        name="OrganizerHome",
        display_name="Home",
        crawled_property="ows_OrganizerHome",
        refinable_alias="Home",
        refinable_string="RefinableString02",
    ),
)

DOCUMENT_CONTENT_TYPE = "Document"


class GraphOfflineError(RuntimeError):
    """Graph drive/listItem surface is unavailable; stamp still writes embeds."""


class GraphDriveClient(Protocol):
    """Delegated Graph drive + listItem surface (live SDK or test fake)."""

    def ensure_site_column(
        self,
        *,
        name: str,
        display_name: str,
        indexed: bool = True,
    ) -> dict: ...

    def add_column_to_document_content_type(self, column_name: str) -> None: ...

    def patch_list_item_fields(self, item_path: str, fields: dict[str, str]) -> None: ...


@dataclass
class FakeGraphDriveClient:
    """In-memory Graph stand-in for listItem field writes (no live SharePoint)."""

    online: bool = True
    site_columns: dict[str, dict] = field(default_factory=dict)
    document_content_type_columns: list[str] = field(default_factory=list)
    item_fields: dict[str, dict[str, str]] = field(default_factory=dict)
    content_type: str = DOCUMENT_CONTENT_TYPE

    def _require_online(self) -> None:
        if not self.online:
            raise GraphOfflineError("graph offline")

    def ensure_site_column(
        self,
        *,
        name: str,
        display_name: str,
        indexed: bool = True,
    ) -> dict:
        self._require_online()
        existing = self.site_columns.get(name)
        if existing is not None:
            return dict(existing)
        col = {
            "name": name,
            "displayName": display_name,
            "indexed": bool(indexed),
            "scope": "site",
        }
        self.site_columns[name] = col
        return dict(col)

    def add_column_to_document_content_type(self, column_name: str) -> None:
        self._require_online()
        if column_name not in self.document_content_type_columns:
            self.document_content_type_columns.append(column_name)

    def patch_list_item_fields(self, item_path: str, fields: dict[str, str]) -> None:
        self._require_online()
        current = dict(self.item_fields.get(item_path) or {})
        current.update({k: str(v) for k, v in fields.items()})
        self.item_fields[item_path] = current

    def walk_folder(self, folder_path: str = "") -> Iterator[str]:
        """Yield known item paths under one folder. No FileLeafRef $filter."""
        self._require_online()
        prefix = folder_path.replace("\\", "/").rstrip("/")
        for item_path in sorted(self.item_fields):
            norm = item_path.replace("\\", "/")
            if not prefix:
                yield item_path
                continue
            if norm == prefix or norm.startswith(prefix + "/"):
                yield item_path
