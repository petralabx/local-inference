from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from harness.config import GraphConfig, PACKAGE_ROOT

GRAPH_RESOURCE = "https://graph.microsoft.com"
GRAPH_SCOPES = ("https://graph.microsoft.com/Sites.ReadWrite.All",)
INTERACTIVE_ENV = "HARNESS_GRAPH_INTERACTIVE"


class GraphAuthError(RuntimeError):
    """Delegated Graph token could not be acquired."""


def cache_file(cfg: GraphConfig) -> Path:
    path = Path(cfg.cache_path)
    if path.is_absolute():
        return path
    return PACKAGE_ROOT / path


def interactive_requested(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(INTERACTIVE_ENV, "").strip().lower() in {"1", "true", "yes"}


def acquire_delegated_token(
    cfg: GraphConfig,
    *,
    interactive: bool | None = None,
    persist: bool = True,
) -> str | None:
    """Return a delegated Graph token, or None when offline / not signed in.

    Order: MSAL silent cache → Azure CLI (same UPN) → device-code when
    interactive. Never prompts for a pasted token. Never app-only.
    """
    if not cfg.enabled:
        return None
    silent = _msal_silent(cfg)
    if silent:
        return silent
    cli_token = _azure_cli_token(cfg.upn)
    if cli_token:
        return cli_token
    if not interactive_requested(interactive):
        return None
    return _msal_device_code(cfg, persist=persist)


def login_delegated(cfg: GraphConfig, *, persist: bool = True) -> str:
    """Interactive device-code login. Writes the MSAL cache for later silent use."""
    token = acquire_delegated_token(cfg, interactive=True, persist=persist)
    if not token:
        raise GraphAuthError("delegated Graph login failed")
    return token


def token_provider_for(cfg: GraphConfig, *, interactive: bool | None = None) -> Callable[[], str] | None:
    token = acquire_delegated_token(cfg, interactive=interactive)
    if not token:
        return None

    def _provide() -> str:
        refreshed = acquire_delegated_token(cfg, interactive=False)
        if not refreshed:
            raise GraphAuthError("delegated Graph token expired and silent refresh failed")
        return refreshed

    return _provide


def _load_msal():
    try:
        import msal  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional until pip install
        raise GraphAuthError("msal is not installed") from exc
    return msal


def _msal_app(cfg: GraphConfig):
    msal = _load_msal()
    cache = msal.SerializableTokenCache()
    path = cache_file(cfg)
    if path.is_file():
        cache.deserialize(path.read_text(encoding="utf-8"))
    authority = f"https://login.microsoftonline.com/{cfg.tenant_id or 'organizations'}"
    app = msal.PublicClientApplication(
        cfg.client_id,
        authority=authority,
        token_cache=cache,
    )
    return msal, app, cache, path


def _persist_cache(cache, path: Path, *, persist: bool) -> None:
    if not persist or not getattr(cache, "has_state_changed", False):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.serialize(), encoding="utf-8")


def _msal_silent(cfg: GraphConfig) -> str | None:
    try:
        _msal, app, cache, path = _msal_app(cfg)
    except GraphAuthError:
        return None
    username = (cfg.upn or "").strip() or None
    accounts = app.get_accounts(username=username) if username else app.get_accounts()
    for account in accounts:
        result = app.acquire_token_silent(list(GRAPH_SCOPES), account=account)
        if result and result.get("access_token"):
            _persist_cache(cache, path, persist=True)
            return str(result["access_token"])
    return None


def _msal_device_code(cfg: GraphConfig, *, persist: bool) -> str | None:
    try:
        _msal, app, cache, path = _msal_app(cfg)
    except GraphAuthError:
        return None
    flow = app.initiate_device_flow(scopes=list(GRAPH_SCOPES))
    if "user_code" not in flow:
        return None
    message = flow.get("message") or (
        "To sign in, open https://microsoft.com/devicelogin and enter the device code."
    )
    print(message, file=sys.stderr)
    result = app.acquire_token_by_device_flow(flow)
    if not result or not result.get("access_token"):
        return None
    _persist_cache(cache, path, persist=persist)
    return str(result["access_token"])


def _azure_cli_token(upn: str) -> str | None:
    """Reuse an existing `az` Graph token when it belongs to the Organizer UPN."""
    show = _run_az(["account", "show", "-o", "json"])
    if show is None:
        return None
    user = show.get("user") if isinstance(show.get("user"), dict) else {}
    name = str(user.get("name") or "").strip().lower()
    if upn and name and name != upn.strip().lower():
        return None
    token_blob = _run_az(
        [
            "account",
            "get-access-token",
            "--resource",
            GRAPH_RESOURCE,
            "-o",
            "json",
        ]
    )
    if token_blob is None:
        return None
    token = token_blob.get("accessToken")
    if not token:
        return None
    return str(token)


def _run_az(args: list[str]) -> dict | None:
    try:
        proc = subprocess.run(
            ["az", *args],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
