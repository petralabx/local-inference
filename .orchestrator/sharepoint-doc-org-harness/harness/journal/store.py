from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JournalAction:
    id: int
    run_id: str
    action_type: str
    payload: dict[str, Any]
    created_at: str
    reversed: int


class ActionJournal:
    """Append-only action journal. Reverse SoT for harness mutations."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              started_at TEXT NOT NULL,
              note TEXT
            );
            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              reversed INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            """
        )
        self._conn.commit()

    def start_run(self, note: str = "") -> str:
        run_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO runs(run_id, started_at, note) VALUES (?, ?, ?)",
            (run_id, _utc_now(), note),
        )
        self._conn.commit()
        return run_id

    def record(self, run_id: str, action_type: str, payload: dict[str, Any]) -> int:
        cur = self._conn.execute(
            "INSERT INTO actions(run_id, action_type, payload_json, created_at, reversed) "
            "VALUES (?, ?, ?, ?, 0)",
            (run_id, action_type, json.dumps(payload), _utc_now()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_actions(self, run_id: str, *, include_reversed: bool = True) -> list[JournalAction]:
        rows = self._conn.execute(
            "SELECT id, run_id, action_type, payload_json, created_at, reversed "
            "FROM actions WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        out: list[JournalAction] = []
        for r in rows:
            if not include_reversed and r["reversed"]:
                continue
            out.append(
                JournalAction(
                    id=r["id"],
                    run_id=r["run_id"],
                    action_type=r["action_type"],
                    payload=json.loads(r["payload_json"]),
                    created_at=r["created_at"],
                    reversed=r["reversed"],
                )
            )
        return out

    def mark_reversed(self, action_id: int) -> None:
        self._conn.execute("UPDATE actions SET reversed = 1 WHERE id = ?", (action_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def os_path(path: Path) -> str:
    """Absolute path. On Windows, prefix \\\\?\\ so names longer than MAX_PATH work."""
    raw = os.path.abspath(os.fspath(path))
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def apply_move(src: Path, dest: Path) -> None:
    src_s = os_path(src)
    dest_s = os_path(dest)
    os.makedirs(os.path.dirname(dest_s), exist_ok=True)
    if os.path.exists(dest_s):
        raise FileExistsError(dest)
    try:
        os.rename(src_s, dest_s)
    except OSError:
        shutil.move(src_s, dest_s)


def reverse_actions(journal: ActionJournal, run_id: str) -> int:
    """Undo rename/move actions for a run in reverse order. Returns count undone."""
    actions = [a for a in journal.list_actions(run_id) if not a.reversed]
    undone = 0
    for action in reversed(actions):
        if action.action_type in {"move", "rename", "archive"}:
            src = Path(action.payload["to"])
            dest = Path(action.payload["from"])
            if src.exists():
                apply_move(src, dest)
            journal.mark_reversed(action.id)
            undone += 1
        elif action.action_type in {"tombstone", "mail_attachment_save"}:
            # Soft marker / ingest record — disk undo for mail is optional later
            journal.mark_reversed(action.id)
            undone += 1
        else:
            raise ValueError(f"Unsupported reverse for action_type={action.action_type}")
    return undone
