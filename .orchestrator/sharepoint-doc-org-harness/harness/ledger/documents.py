from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DocumentRecord:
    sha256: str
    title: str
    prefix: str
    doc_type: str
    doc_date: str
    version: int
    home: str
    current_path: str
    source: str
    created_at: str = ""
    updated_at: str = ""

    def __str__(self) -> str:
        return (
            f"hash={self.sha256} name={Path(self.current_path).name} "
            f"prefix={self.prefix} type={self.doc_type} date={self.doc_date} "
            f"v={self.version} home={self.home} path={self.current_path} "
            f"source={self.source}"
        )


class DocumentLedger:
    """Identity SoT keyed by content hash (ADR 0024). Lives beside the move journal."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
              sha256 TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              prefix TEXT NOT NULL,
              doc_type TEXT NOT NULL,
              doc_date TEXT NOT NULL,
              version INTEGER NOT NULL,
              home TEXT NOT NULL,
              current_path TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert(self, rec: DocumentRecord) -> DocumentRecord:
        now = _utc_now()
        existing = self.get(rec.sha256)
        created = existing.created_at if existing else now
        rec.created_at = created
        rec.updated_at = now
        self._conn.execute(
            """
            INSERT INTO documents (
              sha256, title, prefix, doc_type, doc_date, version,
              home, current_path, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
              title=excluded.title,
              prefix=excluded.prefix,
              doc_type=excluded.doc_type,
              doc_date=excluded.doc_date,
              version=excluded.version,
              home=excluded.home,
              current_path=excluded.current_path,
              source=excluded.source,
              updated_at=excluded.updated_at
            """,
            (
                rec.sha256,
                rec.title,
                rec.prefix,
                rec.doc_type,
                rec.doc_date,
                rec.version,
                rec.home,
                rec.current_path,
                rec.source,
                rec.created_at,
                rec.updated_at,
            ),
        )
        self._conn.commit()
        return rec

    def rekey(self, old_sha256: str, new_sha256: str) -> DocumentRecord | None:
        """Follow content-hash identity after an embed rewrite changes bytes."""
        if old_sha256 == new_sha256:
            return self.get(old_sha256)
        rec = self.get(old_sha256)
        if rec is None:
            return None
        existing = self.get(new_sha256)
        self._conn.execute("DELETE FROM documents WHERE sha256 = ?", (old_sha256,))
        self._conn.commit()
        rec.sha256 = new_sha256
        if existing is not None:
            rec.created_at = existing.created_at
        return self.upsert(rec)

    def get(self, sha256: str) -> DocumentRecord | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return self._from_row(row) if row else None

    def lookup(
        self,
        *,
        path: str | None = None,
        name: str | None = None,
        content_hash: str | None = None,
    ) -> list[DocumentRecord]:
        if content_hash:
            rec = self.get(content_hash)
            return [rec] if rec else []
        rows = self._conn.execute("SELECT * FROM documents").fetchall()
        out: list[DocumentRecord] = []
        for row in rows:
            rec = self._from_row(row)
            if path and path.lower() not in rec.current_path.lower():
                continue
            if name and name.lower() not in Path(rec.current_path).name.lower() and name.lower() not in rec.title.lower():
                continue
            if path or name:
                out.append(rec)
        return out

    def _from_row(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            sha256=row["sha256"],
            title=row["title"],
            prefix=row["prefix"],
            doc_type=row["doc_type"],
            doc_date=row["doc_date"],
            version=int(row["version"]),
            home=row["home"],
            current_path=row["current_path"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
