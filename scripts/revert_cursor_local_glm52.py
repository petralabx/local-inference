#!/usr/bin/env python3
"""Revert Cursor local-glm52 setup and restore pre-override settings."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

STORAGE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl."
    "persistentStorage.applicationUser"
)
STATE_DB = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
BACKUP_GLOB = "cursor-local-glm52-keys-*.json"
MODEL_NAME = "local-glm52"
PROXY_BASE = "http://100.103.33.54:4000/v1"


def latest_backup() -> Path | None:
    backups = sorted(STATE_DB.parent.glob(BACKUP_GLOB))
    return backups[0] if backups else None


def main() -> int:
    if not STATE_DB.exists():
        raise SystemExit(f"Cursor state DB not found: {STATE_DB}")

    backup = latest_backup()
    conn = sqlite3.connect(STATE_DB, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key = ?", (STORAGE_KEY,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"Missing storage key: {STORAGE_KEY}")

        data = json.loads(row[0])
        changes: list[str] = []

        if backup:
            backup_data = json.loads(backup.read_text(encoding="utf-8"))
            restored_app = json.loads(backup_data[STORAGE_KEY])
            data["useOpenAIKey"] = restored_app.get("useOpenAIKey", False)
            data["openAIBaseUrl"] = restored_app.get("openAIBaseUrl", "")
            if "aiSettings" in restored_app:
                data["aiSettings"] = restored_app["aiSettings"]
            models = data.get("availableDefaultModels2", [])
            data["availableDefaultModels2"] = [
                m for m in models if m.get("name") != MODEL_NAME
            ]
            changes.append(f"restored applicationUser from {backup.name}")

            if "cursorAuth/openAIKey" in backup_data:
                cur.execute(
                    "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
                    ("cursorAuth/openAIKey", backup_data["cursorAuth/openAIKey"] or ""),
                )
                changes.append("restored cursorAuth/openAIKey from backup")
        else:
            if data.get("useOpenAIKey"):
                data["useOpenAIKey"] = False
                changes.append("disabled useOpenAIKey")
            if data.get("openAIBaseUrl") == PROXY_BASE:
                data["openAIBaseUrl"] = ""
                changes.append("cleared openAIBaseUrl")
            ai = data.setdefault("aiSettings", {})
            for key in ("userAddedModels", "modelOverrideEnabled"):
                items = ai.get(key, [])
                if MODEL_NAME in items:
                    ai[key] = [x for x in items if x != MODEL_NAME]
                    changes.append(f"removed {MODEL_NAME} from aiSettings.{key}")
            models = data.get("availableDefaultModels2", [])
            before = len(models)
            data["availableDefaultModels2"] = [
                m for m in models if m.get("name") != MODEL_NAME
            ]
            if len(data["availableDefaultModels2"]) != before:
                changes.append(f"removed {MODEL_NAME} from availableDefaultModels2")
            cur.execute("DELETE FROM ItemTable WHERE key = 'cursorAuth/openAIKey'")
            changes.append("cleared cursorAuth/openAIKey")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pre_revert = STATE_DB.with_name(f"cursor-pre-revert-{stamp}.json")
        cur.execute("SELECT value FROM ItemTable WHERE key = 'cursorAuth/openAIKey'")
        auth_row = cur.fetchone()
        pre_revert.write_text(
            json.dumps({STORAGE_KEY: row[0], "cursorAuth/openAIKey": auth_row[0] if auth_row else None}),
            encoding="utf-8",
        )

        cur.execute(
            "UPDATE ItemTable SET value = ? WHERE key = ?",
            (json.dumps(data, separators=(",", ":")), STORAGE_KEY),
        )
        conn.commit()

        print("Reverted Cursor local-glm52 override:")
        for c in changes:
            print(f"  - {c}")
        print(f"\nPre-revert snapshot: {pre_revert.name}")
        print("\nRestart Cursor completely (quit all windows, reopen).")
        print("Then verify in Cursor Settings > Models:")
        print("  - OpenAI API Key toggle OFF (unless you intentionally use BYOK)")
        print("  - Override OpenAI Base URL OFF / empty")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
