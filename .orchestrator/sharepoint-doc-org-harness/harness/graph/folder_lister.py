from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from harness.graph.drive_client import GraphNotFoundError


@dataclass(frozen=True)
class RemoteItem:
    """One file or folder from a per-folder Graph/REST listing."""

    relative_path: str
    name: str
    is_folder: bool
    size: int | None = None
    sha256: str | None = None
    item_id: str | None = None

    @property
    def posix(self) -> str:
        return self.relative_path.replace("\\", "/").strip("/")


@dataclass
class FolderListing:
    files: list[RemoteItem] = field(default_factory=list)
    folders: list[RemoteItem] = field(default_factory=list)
    missing: bool = False


class FolderLister(Protocol):
    """List one folder's children. Never a library-wide unindexed $filter."""

    backend: str

    def list_children(self, folder_rel: str) -> FolderListing: ...


def posix_rel(*parts: str) -> str:
    cleaned = [p.replace("\\", "/").strip("/") for p in parts if p and p.replace("\\", "/").strip("/")]
    return "/".join(cleaned)


def child_rel(folder_rel: str, name: str) -> str:
    return posix_rel(folder_rel, name)


class FolderTree:
    """In-memory library tree used by Graph and REST fakes."""

    def __init__(self) -> None:
        self._files: dict[str, list[RemoteItem]] = {}
        self._folders: dict[str, list[RemoteItem]] = {}
        self._known: set[str] = {""}

    def ensure_folder(self, folder_rel: str) -> None:
        rel = posix_rel(folder_rel)
        self._known.add(rel)
        self._files.setdefault(rel, [])
        self._folders.setdefault(rel, [])
        if not rel:
            return
        parent = posix_rel(str(Path(rel).parent)) if "/" in rel else ""
        name = rel.rsplit("/", 1)[-1]
        self.ensure_folder(parent)
        existing = {item.name.casefold() for item in self._folders[parent]}
        if name.casefold() not in existing:
            self._folders[parent].append(
                RemoteItem(relative_path=rel, name=name, is_folder=True)
            )

    def add_file(
        self,
        relative_path: str,
        *,
        size: int | None = None,
        sha256: str | None = None,
        item_id: str | None = None,
    ) -> RemoteItem:
        rel = posix_rel(relative_path)
        parent = posix_rel(str(Path(rel).parent)) if "/" in rel else ""
        name = rel.rsplit("/", 1)[-1]
        self.ensure_folder(parent)
        item = RemoteItem(
            relative_path=rel,
            name=name,
            is_folder=False,
            size=size,
            sha256=sha256,
            item_id=item_id,
        )
        self._files[parent].append(item)
        return item

    def listing(self, folder_rel: str) -> FolderListing:
        rel = posix_rel(folder_rel)
        if rel not in self._known:
            return FolderListing(missing=True)
        return FolderListing(
            files=list(self._files.get(rel, [])),
            folders=list(self._folders.get(rel, [])),
        )

    @classmethod
    def from_dicts(cls, items: list[dict[str, Any]]) -> FolderTree:
        tree = cls()
        for raw in items:
            path = str(raw.get("path") or raw.get("relative_path") or "")
            if not path:
                continue
            if raw.get("is_folder"):
                tree.ensure_folder(path)
                continue
            sha = raw.get("sha256") or raw.get("sha256Hash")
            tree.add_file(
                path,
                size=int(raw["size"]) if raw.get("size") is not None else None,
                sha256=str(sha) if sha else None,
                item_id=str(raw["item_id"]) if raw.get("item_id") else None,
            )
        return tree


def load_cassette(path: Path) -> FolderTree:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        items = data
    else:
        items = data.get("items") or data.get("files") or []
    if not isinstance(items, list):
        raise ValueError(f"cassette items must be a list: {path}")
    return FolderTree.from_dicts(items)


@dataclass
class FakeGraphFolderLister:
    """Graph drive children stand-in. One list_children call per folder."""

    tree: FolderTree
    backend: str = "fake-graph"
    calls: list[str] = field(default_factory=list)

    def list_children(self, folder_rel: str) -> FolderListing:
        self.calls.append(posix_rel(folder_rel))
        return self.tree.listing(folder_rel)


@dataclass
class FakeSharePointRestLister:
    """SharePoint REST GetFolderByServerRelativeUrl Files/Folders stand-in."""

    tree: FolderTree
    backend: str = "fake-rest"
    file_calls: list[str] = field(default_factory=list)
    folder_calls: list[str] = field(default_factory=list)

    def list_files(self, folder_rel: str) -> list[RemoteItem]:
        rel = posix_rel(folder_rel)
        self.file_calls.append(rel)
        listing = self.tree.listing(rel)
        if listing.missing:
            return []
        return list(listing.files)

    def list_folders(self, folder_rel: str) -> list[RemoteItem]:
        rel = posix_rel(folder_rel)
        self.folder_calls.append(rel)
        listing = self.tree.listing(rel)
        if listing.missing:
            return []
        return list(listing.folders)

    def list_children(self, folder_rel: str) -> FolderListing:
        rel = posix_rel(folder_rel)
        listing = self.tree.listing(rel)
        # REST surfaces Files and Folders as separate GETs per folder.
        files = self.list_files(rel)
        folders = self.list_folders(rel)
        if listing.missing:
            return FolderListing(missing=True)
        return FolderListing(files=files, folders=folders)


def lister_from_cassette(path: Path, *, backend: str = "graph") -> FolderLister:
    tree = load_cassette(path)
    kind = backend.lower().strip()
    if kind in {"rest", "fake-rest", "sharepoint-rest"}:
        return FakeSharePointRestLister(tree)
    return FakeGraphFolderLister(tree)


def _join_url(base: str, suffix: str) -> str:
    return f"{base.rstrip('/')}/{suffix.lstrip('/')}"


class GraphDriveFolderLister:
    """Live Graph drive children listing. Folder-scoped GETs only."""

    backend = "graph"

    def __init__(
        self,
        *,
        drive_id: str,
        token: str,
        base_url: str = "https://graph.microsoft.com/v1.0",
        client: httpx.Client | None = None,
    ) -> None:
        self.drive_id = drive_id
        self._headers = {"Authorization": f"Bearer {token}"}
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=60.0)
        self.calls: list[str] = []

    def _children_url(self, folder_rel: str) -> str:
        rel = posix_rel(folder_rel)
        select = "id,name,size,file,folder"
        if not rel:
            return _join_url(
                self.base_url,
                f"drives/{quote(self.drive_id, safe='')}/root/children?$select={select}",
            )
        encoded = quote(rel, safe="/")
        return _join_url(
            self.base_url,
            f"drives/{quote(self.drive_id, safe='')}/root:/{encoded}:/children?$select={select}",
        )

    def list_children(self, folder_rel: str) -> FolderListing:
        rel = posix_rel(folder_rel)
        self.calls.append(rel)
        url = self._children_url(rel)
        files: list[RemoteItem] = []
        folders: list[RemoteItem] = []
        while url:
            if "$filter" in url.lower():
                raise RuntimeError("graph listing must not use $filter")
            response = self._client.get(url, headers=self._headers)
            if response.status_code == 404:
                return FolderListing(missing=True)
            response.raise_for_status()
            payload = response.json()
            for row in payload.get("value") or []:
                name = str(row.get("name") or "")
                if not name:
                    continue
                child = child_rel(rel, name)
                if row.get("folder") is not None:
                    folders.append(
                        RemoteItem(
                            relative_path=child,
                            name=name,
                            is_folder=True,
                            item_id=str(row["id"]) if row.get("id") else None,
                        )
                    )
                    continue
                file_meta = row.get("file") or {}
                hashes = file_meta.get("hashes") or {}
                sha = hashes.get("sha256Hash") or hashes.get("sha256")
                files.append(
                    RemoteItem(
                        relative_path=child,
                        name=name,
                        is_folder=False,
                        size=int(row["size"]) if row.get("size") is not None else None,
                        sha256=normalize_graph_sha256(sha) if sha else None,
                        item_id=str(row["id"]) if row.get("id") else None,
                    )
                )
            url = payload.get("@odata.nextLink")
        return FolderListing(files=files, folders=folders)


class SharePointRestFolderLister:
    """Live REST GetFolderByServerRelativeUrl Files + Folders. Folder-scoped."""

    backend = "rest"

    def __init__(
        self,
        *,
        site_url: str,
        server_relative_root: str,
        token: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.server_relative_root = "/" + posix_rel(server_relative_root)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;odata=nometadata",
        }
        self._client = client or httpx.Client(timeout=60.0)
        self.file_calls: list[str] = []
        self.folder_calls: list[str] = []

    def _folder_url(self, folder_rel: str, kind: str) -> str:
        rel = posix_rel(folder_rel)
        server = posix_rel(self.server_relative_root, rel)
        server_path = f"/{server}" if server else self.server_relative_root
        quoted = server_path.replace("'", "''")
        return (
            f"{self.site_url}/_api/web/GetFolderByServerRelativeUrl(@p)/{kind}"
            f"?@p='{quoted}'"
        )

    def _get_rows(self, url: str) -> tuple[list[dict[str, Any]], bool]:
        if "$filter" in url.lower():
            raise RuntimeError("sharepoint REST listing must not use $filter")
        response = self._client.get(url, headers=self._headers)
        if response.status_code == 404:
            return [], True
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload, False
        rows = payload.get("value")
        if rows is None and "Name" in payload:
            return [payload], False
        return list(rows or []), False

    def list_files(self, folder_rel: str) -> tuple[list[RemoteItem], bool]:
        rel = posix_rel(folder_rel)
        self.file_calls.append(rel)
        rows, missing = self._get_rows(self._folder_url(rel, "Files"))
        if missing:
            return [], True
        files: list[RemoteItem] = []
        for row in rows:
            name = str(row.get("Name") or row.get("name") or "")
            if not name:
                continue
            files.append(
                RemoteItem(
                    relative_path=child_rel(rel, name),
                    name=name,
                    is_folder=False,
                    size=int(row["Length"]) if row.get("Length") is not None else None,
                    sha256=None,
                )
            )
        return files, False

    def list_folders(self, folder_rel: str) -> tuple[list[RemoteItem], bool]:
        rel = posix_rel(folder_rel)
        self.folder_calls.append(rel)
        rows, missing = self._get_rows(self._folder_url(rel, "Folders"))
        if missing:
            return [], True
        folders: list[RemoteItem] = []
        for row in rows:
            name = str(row.get("Name") or row.get("name") or "")
            if not name or name in {".", ".."}:
                continue
            folders.append(
                RemoteItem(
                    relative_path=child_rel(rel, name),
                    name=name,
                    is_folder=True,
                )
            )
        return folders, False

    def list_children(self, folder_rel: str) -> FolderListing:
        files, files_missing = self.list_files(folder_rel)
        folders, folders_missing = self.list_folders(folder_rel)
        if files_missing or folders_missing:
            return FolderListing(missing=True)
        return FolderListing(files=files, folders=folders)


def normalize_graph_sha256(value: str) -> str:
    """Graph sha256Hash is usually base64; local content_hash is hex."""
    raw = value.strip()
    if not raw:
        return raw
    hexish = all(c in "0123456789abcdefABCDEF" for c in raw) and len(raw) == 64
    if hexish:
        return raw.lower()
    import base64
    import binascii

    try:
        decoded = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError):
        return raw.lower()
    if len(decoded) == 32:
        return decoded.hex()
    return raw.lower()


def listing_from_graph_children(folder_rel: str, rows: list[dict[str, Any]]) -> FolderListing:
    """Map Graph /children rows onto FolderListing. Empty folder/file dicts are truthy via `in`."""
    rel = posix_rel(folder_rel)
    files: list[RemoteItem] = []
    folders: list[RemoteItem] = []
    for row in rows:
        name = str(row.get("name") or "")
        if not name:
            continue
        child = child_rel(rel, name)
        if "folder" in row:
            folders.append(
                RemoteItem(
                    relative_path=child,
                    name=name,
                    is_folder=True,
                    item_id=str(row["id"]) if row.get("id") else None,
                )
            )
            continue
        file_meta = row.get("file") or {}
        hashes = file_meta.get("hashes") or {}
        sha = hashes.get("sha256Hash") or hashes.get("sha256")
        files.append(
            RemoteItem(
                relative_path=child,
                name=name,
                is_folder=False,
                size=int(row["size"]) if row.get("size") is not None else None,
                sha256=normalize_graph_sha256(sha) if sha else None,
                item_id=str(row["id"]) if row.get("id") else None,
            )
        )
    return FolderListing(files=files, folders=folders)


class LiveGraphFolderLister:
    """FolderLister adapter over LiveGraphDriveClient (MSAL token + drive id)."""

    backend = "graph"

    def __init__(self, client: Any) -> None:
        self.client = client
        self.calls: list[str] = []

    def list_children(self, folder_rel: str) -> FolderListing:
        rel = posix_rel(folder_rel)
        self.calls.append(rel)
        try:
            rows = self.client.list_folder_children(rel)
        except GraphNotFoundError:
            return FolderListing(missing=True)
        return listing_from_graph_children(rel, rows)


def lister_from_live_client(client: Any) -> LiveGraphFolderLister:
    return LiveGraphFolderLister(client)


def build_live_lister(
    *,
    backend: str,
    token: str | None,
    drive_id: str | None = None,
    site_url: str | None = None,
    server_relative_root: str | None = None,
    graph_base_url: str = "https://graph.microsoft.com/v1.0",
    client: httpx.Client | None = None,
) -> FolderLister:
    kind = backend.lower().strip()
    if not token:
        raise ValueError("live sync-audit requires an access token")
    if kind == "rest":
        if not site_url or not server_relative_root:
            raise ValueError("REST backend needs site_url and server_relative_root")
        return SharePointRestFolderLister(
            site_url=site_url,
            server_relative_root=server_relative_root,
            token=token,
            client=client,
        )
    if not drive_id:
        raise ValueError("graph backend needs drive_id")
    return GraphDriveFolderLister(
        drive_id=drive_id,
        token=token,
        base_url=graph_base_url,
        client=client,
    )
