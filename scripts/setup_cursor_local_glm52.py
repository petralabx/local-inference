#!/usr/bin/env python3
"""Configure Cursor to use local-glm52 via the Dell LiteLLM proxy.

Updates Cursor's state.vscdb applicationUser blob:
  - useOpenAIKey = true
  - openAIBaseUrl = http://100.103.33.54:4000/v1
  - cursorAuth/openAIKey = LOCAL_LITELLM_MASTER_KEY from .env.local
  - adds local-glm52 as a user model

Important: quit Cursor completely before running (see setup_cursor_local_glm52.ps1).
Do NOT use Developer: Reload Window afterward — account sync can wipe DB-only edits.
Prefer adding the model once via Cursor Settings > Models so it persists on your account.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

STORAGE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl."
    "persistentStorage.applicationUser"
)
STATE_DB = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_LOCAL = REPO_ROOT / ".env.local"
PROXY_BASE = "http://100.103.33.54:4000/v1"
MODEL_NAME = "local-glm52"


def load_master_key() -> str:
    if not ENV_LOCAL.exists():
        raise SystemExit(f"Missing {ENV_LOCAL}")
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("LOCAL_LITELLM_MASTER_KEY="):
            key = line.split("=", 1)[1].strip()
            if not key or key.endswith("CHANGE-ME-generate-a-strong-key"):
                raise SystemExit("LOCAL_LITELLM_MASTER_KEY is unset in .env.local")
            return key
    raise SystemExit("LOCAL_LITELLM_MASTER_KEY not found in .env.local")


def glm_model_entry() -> dict:
    return {
        "name": MODEL_NAME,
        "defaultOn": False,
        "parameterDefinitions": [],
        "variants": [],
        "legacySlugs": [],
        "idAliases": [],
        "cloudAgentEffortModes": [],
        "supportsAgent": True,
        "degradationStatus": 0,
        "supportsThinking": False,
        "supportsImages": False,
        "supportsMaxMode": True,
        "serverModelName": MODEL_NAME,
        "supportsNonMaxMode": True,
        "isRecommendedForBackgroundComposer": False,
        "supportsPlanMode": True,
        "isUserAdded": True,
        "inputboxShortModelName": "GLM 5.2 Local",
        "supportsSandboxing": True,
        "namedModelSectionIndex": 1,
    }


def patch_application_user(data: dict) -> list[str]:
    changes: list[str] = []
    master_key = load_master_key()

    if not data.get("useOpenAIKey"):
        data["useOpenAIKey"] = True
        changes.append("enabled useOpenAIKey")

    if data.get("openAIBaseUrl") != PROXY_BASE:
        data["openAIBaseUrl"] = PROXY_BASE
        changes.append(f"set openAIBaseUrl -> {PROXY_BASE}")

    ai = data.setdefault("aiSettings", {})
    user_added = ai.setdefault("userAddedModels", [])
    if MODEL_NAME not in user_added:
        user_added.append(MODEL_NAME)
        changes.append(f"added {MODEL_NAME} to userAddedModels")

    enabled = ai.setdefault("modelOverrideEnabled", [])
    if MODEL_NAME not in enabled:
        enabled.append(MODEL_NAME)
        changes.append(f"enabled {MODEL_NAME} in model picker")

    models = data.setdefault("availableDefaultModels2", [])
    if not any(m.get("name") == MODEL_NAME for m in models):
        models.append(glm_model_entry())
        changes.append(f"registered {MODEL_NAME} in availableDefaultModels2")

    return changes


def cursor_is_running() -> bool:
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Cursor.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "Cursor.exe" in out.stdout
        except OSError:
            return False
    try:
        out = subprocess.run(["pgrep", "-x", "Cursor"], capture_output=True, check=False)
        return out.returncode == 0
    except OSError:
        return False


def main() -> int:
    if not STATE_DB.exists():
        raise SystemExit(f"Cursor state DB not found: {STATE_DB}")

    if cursor_is_running():
        print(
            "WARNING: Cursor is running. DB edits may not appear in the UI, and "
            "Developer: Reload Window can wipe unsynced model settings.\n"
            "Preferred: quit Cursor, run scripts/setup_cursor_local_glm52.ps1, "
            "or configure once via Cursor Settings > Models.\n"
        )
    master_key = load_master_key()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key_backup = STATE_DB.with_name(f"cursor-local-glm52-keys-{stamp}.json")

    conn = sqlite3.connect(STATE_DB, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key = ?", (STORAGE_KEY,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"Missing storage key: {STORAGE_KEY}")

        cur.execute("SELECT value FROM ItemTable WHERE key = 'cursorAuth/openAIKey'")
        auth_row = cur.fetchone()
        key_backup.write_text(
            json.dumps(
                {
                    STORAGE_KEY: row[0],
                    "cursorAuth/openAIKey": auth_row[0] if auth_row else None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Backed up keys to {key_backup.name}")

        data = json.loads(row[0])
        changes = patch_application_user(data)
        if not changes:
            print("Cursor already configured for local-glm52; no changes needed.")
        else:
            cur.execute(
                "UPDATE ItemTable SET value = ? WHERE key = ?",
                (json.dumps(data, separators=(",", ":")), STORAGE_KEY),
            )
            print("Updated applicationUser:")
            for c in changes:
                print(f"  - {c}")

        if auth_row and auth_row[0] == master_key:
            print("cursorAuth/openAIKey already set.")
        else:
            cur.execute(
                "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
                ("cursorAuth/openAIKey", master_key),
            )
            print("Updated cursorAuth/openAIKey from .env.local")

        conn.commit()
    finally:
        conn.close()

    print()
    print("Done.")
    print("If Cursor was closed: reopen it normally (not Reload Window).")
    print("If Cursor is still open: use Cursor Settings > Models (steps below) — do not reload.")
    print(f"Then pick model '{MODEL_NAME}' (shown as 'GLM 5.2 Local') in Chat/Agent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
