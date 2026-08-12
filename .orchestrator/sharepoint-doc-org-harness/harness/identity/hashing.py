from __future__ import annotations

import hashlib
from pathlib import Path


def content_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def file_identity(path: Path) -> dict[str, str | int]:
    st = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": content_hash(path),
    }
