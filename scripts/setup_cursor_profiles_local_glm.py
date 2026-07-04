#!/usr/bin/env python3
"""Configure Cursor Default + Local GLM profiles for local-glm52.

- DEFAULT profile: cloud models only (no OpenAI override, no bogus API key)
- Local GLM profile: OpenAI override -> LiteLLM proxy, model local-glm52

Quit Cursor before running for best results; safe to run while open but restart after.
"""
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
USER_DIR = Path(os.environ["APPDATA"]) / "Cursor" / "User"
DEFAULT_DB = USER_DIR / "globalStorage" / "state.vscdb"
STORAGE_JSON = USER_DIR / "globalStorage" / "storage.json"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_LOCAL = REPO_ROOT / ".env.local"
PROXY_BASE = "http://100.103.33.54:4000/v1"
MODEL_NAME = "local-glm52"
PROFILE_NAME = "Local GLM"


def load_master_key() -> str:
    if not ENV_LOCAL.exists():
        raise SystemExit(f"Missing {ENV_LOCAL}")
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("LOCAL_LITELLM_MASTER_KEY="):
            key = line.split("=", 1)[1].strip()
            if not key or "CHANGE-ME" in key:
                raise SystemExit("LOCAL_LITELLM_MASTER_KEY is unset in .env.local")
            return key
    raise SystemExit("LOCAL_LITELLM_MASTER_KEY not found in .env.local")


def glm_model_entry() -> dict:
    return {
        "name": MODEL_NAME,
        "defaultOn": True,
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


def find_local_glm_profile_id() -> str:
    if not STORAGE_JSON.exists():
        raise SystemExit(f"Missing {STORAGE_JSON}")
    storage = json.loads(STORAGE_JSON.read_text(encoding="utf-8"))
    for profile in storage.get("userDataProfiles", []):
        if profile.get("name") == PROFILE_NAME:
            loc = profile.get("location")
            if loc:
                return str(loc)
    raise SystemExit(
        f'Profile "{PROFILE_NAME}" not found. Create it in Cursor first '
        "(File -> Preferences -> Profiles -> New Profile)."
    )


def ensure_profile_flags() -> None:
    storage = json.loads(STORAGE_JSON.read_text(encoding="utf-8"))
    changed = False
    for profile in storage.get("userDataProfiles", []):
        if profile.get("name") != PROFILE_NAME:
            continue
        flags = profile.setdefault("useDefaultFlags", {})
        for key in ("keybindings", "tasks", "snippets", "extensions"):
            if not flags.get(key):
                flags[key] = True
                changed = True
    if changed:
        STORAGE_JSON.write_text(json.dumps(storage, indent=4), encoding="utf-8")
        print("Updated storage.json: Local GLM profile inherits Default extensions/keybindings.")


def read_application_user(conn: sqlite3.Connection) -> dict | None:
    cur = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key = ?", (STORAGE_KEY,))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None


def write_application_user(conn: sqlite3.Connection, data: dict) -> None:
    cur = conn.cursor()
    payload = json.dumps(data, separators=(",", ":"))
    cur.execute("SELECT 1 FROM ItemTable WHERE key = ?", (STORAGE_KEY,))
    if cur.fetchone():
        cur.execute("UPDATE ItemTable SET value = ? WHERE key = ?", (payload, STORAGE_KEY))
    else:
        cur.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            (STORAGE_KEY, payload),
        )


def set_openai_key(conn: sqlite3.Connection, key: str | None) -> None:
    cur = conn.cursor()
    if key:
        cur.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("cursorAuth/openAIKey", key),
        )
    else:
        cur.execute("DELETE FROM ItemTable WHERE key = 'cursorAuth/openAIKey'")


def remove_glm_from_data(data: dict) -> list[str]:
    changes: list[str] = []
    if data.get("useOpenAIKey"):
        data["useOpenAIKey"] = False
        changes.append("disabled useOpenAIKey")
    if data.get("openAIBaseUrl"):
        data["openAIBaseUrl"] = ""
        changes.append("cleared openAIBaseUrl")

    ai = data.setdefault("aiSettings", {})
    for field in ("userAddedModels", "modelOverrideEnabled"):
        items = ai.get(field, [])
        if MODEL_NAME in items:
            ai[field] = [x for x in items if x != MODEL_NAME]
            changes.append(f"removed {MODEL_NAME} from aiSettings.{field}")

    models = data.get("availableDefaultModels2", [])
    filtered = [m for m in models if m.get("name") != MODEL_NAME]
    if len(filtered) != len(models):
        data["availableDefaultModels2"] = filtered
        changes.append(f"removed {MODEL_NAME} from availableDefaultModels2")
    return changes


def apply_glm_to_data(data: dict) -> list[str]:
    changes: list[str] = []
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
    if enabled != [MODEL_NAME]:
        ai["modelOverrideEnabled"] = [MODEL_NAME]
        changes.append(f"model picker limited to {MODEL_NAME} only")

    disabled = ai.setdefault("modelOverrideDisabled", [])
    # Keep cloud models out of the Local GLM picker to avoid BYOK errors.
    _ = disabled

    models = data.setdefault("availableDefaultModels2", [])
    existing = next((m for m in models if m.get("name") == MODEL_NAME), None)
    if existing:
        if not existing.get("defaultOn"):
            existing["defaultOn"] = True
            changes.append(f"set {MODEL_NAME} as defaultOn in catalog")
    else:
        models.append(glm_model_entry())
        changes.append(f"registered {MODEL_NAME} in availableDefaultModels2")

    return changes


def backup_db_state(default_data: dict | None, local_data: dict | None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = DEFAULT_DB.parent / f"cursor-profile-setup-backup-{stamp}.json"
    path.write_text(
        json.dumps({"default_applicationUser": default_data, "local_applicationUser": local_data}, indent=2),
        encoding="utf-8",
    )
    return path


def configure_db(db_path: Path, label: str, patch_fn, master_key: str | None) -> list[str]:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        data = read_application_user(conn)
        if data is None:
            raise SystemExit(f"{label}: missing applicationUser — open that profile in Cursor once, then re-run.")
        changes = patch_fn(data)
        if changes:
            write_application_user(conn, data)
        if master_key is not None:
            set_openai_key(conn, master_key)
            changes.append("set cursorAuth/openAIKey from .env.local")
        elif label == "DEFAULT":
            set_openai_key(conn, None)
            changes.append("cleared cursorAuth/openAIKey")
        conn.commit()
        return changes
    finally:
        conn.close()


def main() -> int:
    profile_id = find_local_glm_profile_id()
    local_db = USER_DIR / "profiles" / profile_id / "globalStorage" / "state.vscdb"
    if not DEFAULT_DB.exists():
        raise SystemExit(f"Missing default state DB: {DEFAULT_DB}")
    if not local_db.exists():
        raise SystemExit(
            f"Missing Local GLM state DB: {local_db}\n"
            f'Open Cursor, switch to profile "{PROFILE_NAME}", then re-run.'
        )

    master_key = load_master_key()
    ensure_profile_flags()

    default_before = read_application_user(sqlite3.connect(f"file:{DEFAULT_DB}?mode=ro", uri=True))
    local_before = read_application_user(sqlite3.connect(f"file:{local_db}?mode=ro", uri=True))

    # Bootstrap Local GLM profile from Default if never opened with models UI
    if local_before is None:
        if default_before is None:
            raise SystemExit("Default profile has no applicationUser; open Cursor once and re-run.")
        conn = sqlite3.connect(local_db, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            seeded = json.loads(json.dumps(default_before))
            write_application_user(conn, seeded)
            conn.commit()
            print(f"Seeded Local GLM profile DB from Default template.")
        finally:
            conn.close()

    backup = backup_db_state(
        default_before if isinstance(default_before, dict) else None,
        local_before if isinstance(local_before, dict) else None,
    )
    print(f"Backup: {backup.name}")

    default_changes = configure_db(DEFAULT_DB, "DEFAULT", remove_glm_from_data, None)
    local_changes = configure_db(local_db, "Local GLM", apply_glm_to_data, master_key)

    print("\nDEFAULT profile:")
    for c in default_changes or ["already clean"]:
        print(f"  - {c}")

    print(f"\nLocal GLM profile ({profile_id}):")
    for c in local_changes or ["already configured"]:
        print(f"  - {c}")

    print("\nDone. Fully quit Cursor (all windows), reopen on DEFAULT profile.")
    print("For local inference: switch profile to 'Local GLM' and use model local-glm52 only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
