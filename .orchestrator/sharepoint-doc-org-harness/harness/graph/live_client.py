from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse

import httpx

from harness.graph.drive_client import DOCUMENT_CONTENT_TYPE, GraphConflictError, GraphNotFoundError, GraphOfflineError

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# Document CT 0x0101 and its Graph-encoded form. Never invent a custom CT.
DOCUMENT_CT_PREFIX = "0x0101"
# Simple PUT /content is only for files smaller than 4 MiB.
SIMPLE_UPLOAD_MAX_BYTES = 4 * 1024 * 1024
# Upload-session chunks must be a multiple of 320 KiB (10 MiB = 32 * 320 KiB).
UPLOAD_CHUNK_SIZE = 10 * 1024 * 1024
UPLOAD_TIMEOUT_SECONDS = 300.0


def parse_site_url(site_url: str) -> tuple[str, str]:
    parsed = urlparse(site_url)
    host = parsed.netloc or "petrasoap.sharepoint.com"
    path = parsed.path.rstrip("/") or "/sites/VincePersonal"
    if not path.startswith("/"):
        path = "/" + path
    return host, path


def library_relative_path(item_path: str, sync_root: Path | None) -> str:
    """Map a local sync path (or already-relative path) onto the library."""
    raw = str(item_path).replace("\\", "/").strip()
    if not raw:
        raise GraphOfflineError("empty item path")
    if sync_root is not None:
        root = str(sync_root).replace("\\", "/").rstrip("/")
        if raw.lower().startswith(root.lower() + "/"):
            raw = raw[len(root) + 1 :]
        elif raw.lower() == root.lower():
            raw = ""
    return raw.lstrip("/")


def encode_drive_path(rel: str) -> str:
    return quote(rel.replace("\\", "/").lstrip("/"), safe="/")


class LiveGraphDriveClient:
    """Delegated Graph drive + listItem client. Path/folder walk; no FileLeafRef $filter."""

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        site_url: str,
        library: str = "Documents",
        sync_root: Path | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.site_url = site_url
        self.library = library
        self.sync_root = Path(sync_root) if sync_root is not None else None
        self._http = http
        self._owns_http = http is None
        self._site_id: str | None = None
        self._drive_id: str | None = None
        self._list_id: str | None = None
        self._column_ids: dict[str, str] = {}
        self._document_ct_id: str | None = None

    def close(self) -> None:
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None

    def ensure_site_column(
        self,
        *,
        name: str,
        display_name: str,
        indexed: bool = True,
    ) -> dict:
        existing = self._find_site_column(name)
        if existing is not None:
            return existing
        body = {
            "name": name,
            "displayName": display_name,
            "hidden": False,
            "indexed": bool(indexed),
            "text": {"allowMultipleLines": False, "maxLength": 255},
        }
        created = self._request_json("POST", f"/sites/{self.site_id()}/columns", json=body)
        col = _column_payload(created)
        self._column_ids[name] = str(created.get("id") or "")
        return col

    def add_column_to_document_content_type(self, column_name: str) -> None:
        ct_id = self.document_content_type_id()
        existing = self._content_type_column_names(ct_id)
        if column_name in existing:
            return
        column_id = self._column_ids.get(column_name)
        if not column_id:
            found = self._find_site_column(column_name)
            if found is None:
                raise GraphOfflineError(f"site column missing: {column_name}")
            column_id = self._column_ids.get(column_name)
        if not column_id:
            raise GraphOfflineError(f"site column id missing: {column_name}")
        bind = f"{GRAPH_ROOT}/sites/{self.site_id()}/columns/{column_id}"
        self._request_json(
            "POST",
            f"/sites/{self.site_id()}/contentTypes/{ct_id}/columns",
            json={"sourceColumn@odata.bind": bind},
        )

    def patch_list_item_fields(self, item_path: str, fields: dict[str, str]) -> None:
        rel = library_relative_path(item_path, self.sync_root)
        if not rel:
            raise GraphOfflineError("cannot patch library root")
        item = self._item_by_path(rel)
        list_item_id = _list_item_id(item)
        if not list_item_id:
            list_item = self._request_json(
                "GET",
                f"/drives/{self.drive_id()}/items/{item['id']}/listItem",
            )
            list_item_id = str(list_item.get("id") or "")
        if not list_item_id:
            raise GraphOfflineError(f"listItem missing for {rel}")
        self._request_json(
            "PATCH",
            f"/sites/{self.site_id()}/lists/{self.list_id()}/items/{list_item_id}/fields",
            json={k: str(v) for k, v in fields.items()},
        )

    def walk_folder(self, folder_path: str = "") -> Iterator[dict[str, Any]]:
        """Yield drive items under one folder by paging /children (not list $filter)."""
        rel = library_relative_path(folder_path, self.sync_root)
        stack = [rel]
        while stack:
            current = stack.pop()
            for child in self.list_folder_children(current):
                child_rel = _child_rel(current, child)
                # Graph sends "folder": {} / "file": {} — empty dicts are falsy.
                if "folder" in child:
                    stack.append(child_rel)
                    continue
                if "file" in child or child.get("name"):
                    yield {**child, "libraryPath": child_rel}

    def list_folder_children(self, folder_rel: str) -> list[dict[str, Any]]:
        encoded = encode_drive_path(folder_rel)
        if encoded:
            path = f"/drives/{self.drive_id()}/root:/{encoded}:/children"
        else:
            path = f"/drives/{self.drive_id()}/root/children"
        rows: list[dict[str, Any]] = []
        url: str | None = path
        while url:
            data = self._request_json("GET", url)
            rows.extend(data.get("value") or [])
            nxt = data.get("@odata.nextLink")
            url = str(nxt) if nxt else None
        return rows

    def get_item_by_path(self, item_path: str) -> dict[str, Any] | None:
        rel = library_relative_path(item_path, self.sync_root)
        if not rel:
            return {"name": "root", "folder": {}, "size": 0}
        try:
            return self._item_by_path(rel)
        except GraphNotFoundError:
            return None

    def ensure_folder_path(self, folder_path: str) -> None:
        rel = library_relative_path(folder_path, self.sync_root)
        if not rel:
            return
        parts = [p for p in rel.split("/") if p]
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            existing = self.get_item_by_path(current)
            if existing is not None:
                continue
            parent = str(Path(current).parent).replace("\\", "/")
            if parent == ".":
                parent = ""
            self._create_folder(parent, part)

    def upload_file(
        self,
        local_path: Path | str,
        library_path: str | None = None,
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        src = Path(local_path)
        if not src.is_file():
            raise GraphOfflineError(f"upload source missing: {src}")
        rel = library_relative_path(library_path or str(src), self.sync_root)
        if not rel:
            raise GraphOfflineError("cannot upload to library root")
        size = src.stat().st_size
        existing = self.get_item_by_path(rel)
        if existing is not None and "file" in existing:
            existing_size = existing.get("size")
            if existing_size is not None and int(existing_size) == size:
                return {
                    "path": rel,
                    "status": "skipped_identical",
                    "size": size,
                    "mode": "none",
                }
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
        if size < SIMPLE_UPLOAD_MAX_BYTES:
            mode = "simple"
            self._put_content(rel, src, replace=(status == "replaced"))
        else:
            mode = "session"
            self._upload_session(rel, src, size=size, replace=(status == "replaced"))
        return {"path": rel, "status": status, "size": size, "mode": mode}

    def _create_folder(self, parent_rel: str, name: str) -> None:
        encoded = encode_drive_path(parent_rel)
        if encoded:
            path = f"/drives/{self.drive_id()}/root:/{encoded}:/children"
        else:
            path = f"/drives/{self.drive_id()}/root/children"
        body = {
            "name": name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }
        try:
            self._request_json("POST", path, json=body)
        except GraphOfflineError as exc:
            if "409" in str(exc) or "nameAlreadyExists" in str(exc):
                return
            raise

    def _put_content(self, rel: str, src: Path, *, replace: bool) -> dict[str, Any]:
        encoded = encode_drive_path(rel)
        behavior = "replace" if replace else "fail"
        url = (
            f"{GRAPH_ROOT}/drives/{self.drive_id()}/root:/{encoded}:/content"
            f"?@microsoft.graph.conflictBehavior={behavior}"
        )
        data = src.read_bytes()
        return self._request_bytes(
            "PUT", url, content=data, content_type="application/octet-stream"
        )

    def _upload_session(self, rel: str, src: Path, *, size: int, replace: bool) -> dict[str, Any]:
        encoded = encode_drive_path(rel)
        behavior = "replace" if replace else "fail"
        session = self._request_json(
            "POST",
            f"/drives/{self.drive_id()}/root:/{encoded}:/createUploadSession",
            json={"item": {"@microsoft.graph.conflictBehavior": behavior}},
        )
        upload_url = str(session.get("uploadUrl") or "")
        if not upload_url:
            raise GraphOfflineError(f"upload session missing url for {rel}")
        if "FileLeafRef" in upload_url:
            raise GraphOfflineError("refusing FileLeafRef $filter (5k throttle)")
        sent = 0
        last: dict[str, Any] = {}
        with src.open("rb") as handle:
            while sent < size:
                chunk = handle.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                end = sent + len(chunk) - 1
                last = self._put_session_chunk(
                    upload_url,
                    chunk,
                    start=sent,
                    end=end,
                    total=size,
                )
                sent = end + 1
        return last

    def _put_session_chunk(
        self,
        upload_url: str,
        chunk: bytes,
        *,
        start: int,
        end: int,
        total: int,
    ) -> dict[str, Any]:
        headers = {
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Type": "application/octet-stream",
        }
        try:
            resp = self._client().put(
                upload_url,
                headers=headers,
                content=chunk,
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise GraphOfflineError(f"graph transport: {exc.__class__.__name__}") from exc
        if resp.status_code in {401, 403}:
            raise GraphOfflineError(f"graph auth {resp.status_code}")
        if resp.status_code == 404:
            raise GraphNotFoundError(f"404 PUT upload-session")
        if resp.status_code >= 400:
            raise GraphOfflineError(f"graph {resp.status_code}")
        if resp.status_code == 202 or not resp.content:
            return {}
        try:
            data = resp.json()
        except ValueError as exc:
            raise GraphOfflineError("graph non-json") from exc
        return data if isinstance(data, dict) else {"value": data}

    def site_id(self) -> str:
        if self._site_id:
            return self._site_id
        host, path = parse_site_url(self.site_url)
        data = self._request_json("GET", f"/sites/{host}:{path}")
        site_id = str(data.get("id") or "")
        if not site_id:
            raise GraphOfflineError(f"site not found: {self.site_url}")
        self._site_id = site_id
        return site_id

    def drive_id(self) -> str:
        if self._drive_id:
            return self._drive_id
        data = self._request_json("GET", f"/sites/{self.site_id()}/drive")
        drive_id = str(data.get("id") or "")
        if not drive_id:
            raise GraphOfflineError("default drive missing")
        self._drive_id = drive_id
        ids = data.get("sharePointIds") or data.get("sharepointIds") or {}
        if ids.get("listId"):
            self._list_id = str(ids["listId"])
        return drive_id

    def list_id(self) -> str:
        if self._list_id:
            return self._list_id
        self.drive_id()
        if self._list_id:
            return self._list_id
        wanted = (self.library or "Documents").strip().lower()
        data = self._request_json("GET", f"/sites/{self.site_id()}/lists")
        for row in data.get("value") or []:
            name = str(row.get("name") or "").lower()
            display = str(row.get("displayName") or "").lower()
            if name == wanted or display == wanted or display == "shared documents":
                self._list_id = str(row.get("id") or "")
                break
        if not self._list_id:
            raise GraphOfflineError(f"library not found: {self.library}")
        return self._list_id

    def document_content_type_id(self) -> str:
        if self._document_ct_id:
            return self._document_ct_id
        data = self._request_json("GET", f"/sites/{self.site_id()}/contentTypes")
        exact = None
        prefix_hit = None
        named = None
        for row in data.get("value") or []:
            cid = str(row.get("id") or "")
            name = str(row.get("name") or "")
            if cid.upper() == DOCUMENT_CT_PREFIX:
                exact = cid
            elif cid.upper().startswith(DOCUMENT_CT_PREFIX) and prefix_hit is None:
                prefix_hit = cid
            if name == DOCUMENT_CONTENT_TYPE and named is None:
                named = cid
        chosen = exact or named or prefix_hit
        if not chosen:
            raise GraphOfflineError("Document content type 0x0101 not found")
        self._document_ct_id = chosen
        return chosen

    def _find_site_column(self, name: str) -> dict | None:
        data = self._request_json("GET", f"/sites/{self.site_id()}/columns")
        for row in data.get("value") or []:
            if str(row.get("name") or "") == name:
                self._column_ids[name] = str(row.get("id") or "")
                return _column_payload(row)
        return None

    def _content_type_column_names(self, ct_id: str) -> set[str]:
        data = self._request_json(
            "GET",
            f"/sites/{self.site_id()}/contentTypes/{ct_id}/columns",
        )
        return {str(row.get("name") or "") for row in data.get("value") or []}

    def _item_by_path(self, rel: str) -> dict[str, Any]:
        encoded = encode_drive_path(rel)
        return self._request_json(
            "GET",
            f"/drives/{self.drive_id()}/root:/{encoded}",
        )

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=60.0)
        return self._http

    def _headers(self) -> dict[str, str]:
        try:
            token = self.token_provider()
        except Exception as exc:
            raise GraphOfflineError("graph token unavailable") from exc
        if not token:
            raise GraphOfflineError("graph token empty")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request_json(self, method: str, path_or_url: str, **kwargs: Any) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else f"{GRAPH_ROOT}{path_or_url}"
        if "FileLeafRef" in url:
            raise GraphOfflineError("refusing FileLeafRef $filter (5k throttle)")
        try:
            resp = self._client().request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise GraphOfflineError(f"graph transport: {exc.__class__.__name__}") from exc
        if resp.status_code in {401, 403}:
            raise GraphOfflineError(f"graph auth {resp.status_code}")
        if resp.status_code == 404:
            raise GraphNotFoundError(f"404 {method} {url}")
        if resp.status_code == 409:
            raise GraphConflictError(f"graph 409 conflict {method} {url}")
        if resp.status_code >= 400:
            raise GraphOfflineError(f"graph {resp.status_code}")
        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            data = resp.json()
        except ValueError as exc:
            raise GraphOfflineError("graph non-json") from exc
        return data if isinstance(data, dict) else {"value": data}

    def _request_bytes(
        self,
        method: str,
        url: str,
        *,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        if "FileLeafRef" in url:
            raise GraphOfflineError("refusing FileLeafRef $filter (5k throttle)")
        headers = self._headers()
        headers["Content-Type"] = content_type
        try:
            resp = self._client().request(
                method,
                url,
                headers=headers,
                content=content,
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise GraphOfflineError(f"graph transport: {exc.__class__.__name__}") from exc
        if resp.status_code in {401, 403}:
            raise GraphOfflineError(f"graph auth {resp.status_code}")
        if resp.status_code == 404:
            raise GraphNotFoundError(f"404 {method} {url}")
        if resp.status_code == 409:
            raise GraphConflictError(f"graph 409 conflict {method}")
        if resp.status_code >= 400:
            raise GraphOfflineError(f"graph {resp.status_code}")
        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            data = resp.json()
        except ValueError as exc:
            raise GraphOfflineError("graph non-json") from exc
        return data if isinstance(data, dict) else {"value": data}


def _column_payload(row: dict[str, Any]) -> dict:
    return {
        "name": str(row.get("name") or ""),
        "displayName": str(row.get("displayName") or ""),
        "indexed": bool(row.get("indexed", True)),
        "scope": "site",
        "id": str(row.get("id") or ""),
    }


def _list_item_id(item: dict[str, Any]) -> str:
    ids = item.get("sharePointIds") or item.get("sharepointIds") or {}
    raw = ids.get("listItemId") or item.get("listItemId")
    if raw:
        return str(raw)
    nested = item.get("listItem") or {}
    return str(nested.get("id") or "")


def _child_rel(folder_rel: str, child: dict[str, Any]) -> str:
    name = str(child.get("name") or "")
    if folder_rel:
        return f"{folder_rel.rstrip('/')}/{name}"
    return name
