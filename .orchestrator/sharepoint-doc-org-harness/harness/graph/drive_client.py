from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

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


class GraphNotFoundError(GraphOfflineError):
    """Drive item path is missing (HTTP 404)."""


class GraphConflictError(GraphOfflineError):
    """Server item exists with a different size and replace was not requested."""


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

    def walk_folder(self, folder_path: str = "") -> Iterator: ...

    def get_item_by_path(self, item_path: str) -> dict[str, Any] | None: ...

    def ensure_folder_path(self, folder_path: str) -> None: ...

    def upload_file(
        self,
        local_path: Path | str,
        library_path: str | None = None,
        *,
        replace: bool = False,
    ) -> dict[str, Any]: ...


def _posix_rel(item_path: str) -> str:
    return item_path.replace("\\", "/").strip("/")


@dataclass
class FakeGraphDriveClient:
    """In-memory Graph stand-in for listItem field writes (no live SharePoint)."""

    online: bool = True
    site_columns: dict[str, dict] = field(default_factory=dict)
    document_content_type_columns: list[str] = field(default_factory=list)
    item_fields: dict[str, dict[str, str]] = field(default_factory=dict)
    content_type: str = DOCUMENT_CONTENT_TYPE
    server_files: dict[str, dict[str, Any]] = field(default_factory=dict)
    folders: set[str] = field(default_factory=lambda: {""})
    upload_calls: list[dict[str, Any]] = field(default_factory=list)
    simple_upload_max_bytes: int = 4 * 1024 * 1024

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
        keys = set(self.item_fields) | set(self.server_files)
        for item_path in sorted(keys):
            norm = item_path.replace("\\", "/")
            if not prefix:
                yield item_path
                continue
            if norm == prefix or norm.startswith(prefix + "/"):
                yield item_path

    def get_item_by_path(self, item_path: str) -> dict[str, Any] | None:
        self._require_online()
        rel = _posix_rel(item_path)
        if not rel:
            return {"name": "root", "folder": {}, "size": 0}
        stored = self.server_files.get(rel)
        if stored is not None:
            return {
                "name": Path(rel).name,
                "size": stored.get("size"),
                "file": {},
                "libraryPath": rel,
            }
        if rel in self.item_fields:
            return {"name": Path(rel).name, "file": {}, "libraryPath": rel}
        return None

    def ensure_folder_path(self, folder_path: str) -> None:
        self._require_online()
        rel = _posix_rel(folder_path)
        if not rel:
            self.folders.add("")
            return
        parts = rel.split("/")
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            self.folders.add(current)

    def upload_file(
        self,
        local_path: Path | str,
        library_path: str | None = None,
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        self._require_online()
        src = Path(local_path)
        rel = _posix_rel(library_path or str(src))
        if not rel:
            raise GraphOfflineError("cannot upload to library root")
        size = src.stat().st_size if src.is_file() else 0
        existing = self.get_item_by_path(rel)
        if existing is not None and "file" in existing:
            existing_size = existing.get("size")
            if existing_size is not None and int(existing_size) == size:
                call = {"path": rel, "status": "skipped_identical", "size": size, "mode": "none"}
                self.upload_calls.append(call)
                return call
            if not replace:
                raise GraphConflictError(
                    f"server item exists with different size: {rel} "
                    f"local={size} server={existing_size}"
                )
            status = "replaced"
        else:
            status = "uploaded"
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        self.ensure_folder_path(parent)
        payload = src.read_bytes() if src.is_file() else b""
        mode = "simple" if size < self.simple_upload_max_bytes else "session"
        self.server_files[rel] = {"size": size, "content": payload, "mode": mode}
        call = {"path": rel, "status": status, "size": size, "mode": mode}
        self.upload_calls.append(call)
        return call
