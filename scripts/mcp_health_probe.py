#!/usr/bin/env python3
"""Scheduled health probe for every enabled MCP target in ``.mcp.json``.

Runs the ``smoke_mcp_targets`` checks (initialize, discovery, self-check) per
enabled target, records last-good / last-error state in a JSON file outside
the tree, and emits a deduplicated alert only when something changes:

  ok -> failing, failing -> recovered, or a failing target's category changes.
  An unchanged failure re-alerts only after ``--realert-after`` hours.

A target is enabled unless ``"smoke": {"enabled": false}`` is set for it in
``.mcp.json``. Credentials come from the environment at run time and are never
written to state or alerts. ``--status`` / ``--json`` read state only (no
probing) and exit 1 if any enabled target is currently failing.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
STATE_VERSION = 1
DEFAULT_REALERT_HOURS = 6.0
WEBHOOK_ENV = "MCP_HEALTH_WEBHOOK_URL"
STATE_ENV = "MCP_HEALTH_STATE"
MAX_DETAIL = 500

OK, FAILING, SKIPPED_STATUS, DISABLED = "ok", "failing", "skipped", "disabled"


def _load_harness():
    existing = sys.modules.get("smoke_mcp_targets")
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        "smoke_mcp_targets", SCRIPTS_DIR / "smoke_mcp_targets.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_mcp_targets"] = module
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


def default_state_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if env.get(STATE_ENV):
        return Path(env[STATE_ENV])
    if os.name == "nt":
        base = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "local-inference" / "mcp-health.json"


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_enabled(config_path: Path) -> dict[str, bool]:
    """Per-target enabled flag from the raw config; default True."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    flags: dict[str, bool] = {}
    for name, spec in (config.get("mcpServers") or {}).items():
        smoke = spec.get("smoke") if isinstance(spec.get("smoke"), dict) else {}
        flags[name] = smoke.get("enabled", True) is not False
    return flags


# --- state ---------------------------------------------------------------

def empty_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "targets": {}}


def load_state(path: Path) -> tuple[dict[str, Any], str | None]:
    """Return (state, warning). A corrupt file is moved aside, not deleted."""
    if not path.exists():
        return empty_state(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("targets"), dict):
            raise ValueError("unexpected state shape")
        return data, None
    except (OSError, ValueError) as exc:
        aside = path.with_name(path.name + ".corrupt")
        try:
            os.replace(path, aside)
            note = f"moved to {aside}"
        except OSError:
            note = "could not move aside"
        return empty_state(), f"state file {path} unreadable ({exc}); {note}; starting fresh"


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomic write: temp file in the same directory, fsync, rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_entry() -> dict[str, Any]:
    return {
        "status": "unknown",
        "last_checked_at": None,
        "last_ok_at": None,
        "last_error_at": None,
        "last_error_category": None,
        "last_error_detail": None,
        "consecutive_failures": 0,
        "alert_category": None,  # category of the currently open alert
        "last_alert_at": None,
    }


# --- alert sinks ---------------------------------------------------------

class StdoutSink:
    """JSON lines on stdout."""

    def emit(self, alert: dict[str, Any]) -> bool:
        print(json.dumps(alert, sort_keys=True), flush=True)
        return True


class WebhookSink:
    """POSTs the alert as JSON. The URL is a secret: never logged."""

    def __init__(self, url: str, timeout: float = 10.0):
        self._url = url
        self._timeout = timeout

    def emit(self, alert: dict[str, Any]) -> bool:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(alert).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout):
                return True
        except Exception as exc:
            print(f"warning: webhook alert failed ({type(exc).__name__})", file=sys.stderr)
            return False


class MultiSink:
    def __init__(self, sinks: list[Any]):
        self._sinks = sinks

    def emit(self, alert: dict[str, Any]) -> bool:
        return all([sink.emit(alert) for sink in self._sinks])


def build_sink(env: Mapping[str, str]) -> Any:
    sinks: list[Any] = [StdoutSink()]
    if env.get(WEBHOOK_ENV):
        sinks.append(WebhookSink(env[WEBHOOK_ENV]))
    return MultiSink(sinks)


# --- probing -------------------------------------------------------------

Probe = Callable[[Any, Mapping[str, str], float], Any]


def real_probe(target: Any, env: Mapping[str, str], timeout: float) -> Any:
    return asyncio.run(harness.smoke_target(target, env, timeout))


def _clean_detail(detail: str, target: Any, env: Mapping[str, str]) -> str:
    redact = harness.make_redactor([env.get(n, "") for n in target.required_env])
    return redact(detail)[:MAX_DETAIL]


def apply_result(
    entry: dict[str, Any],
    result: Any,
    detail: str,
    now: datetime,
    realert_after: timedelta,
) -> dict[str, Any] | None:
    """Update ``entry`` in place; return an alert dict (sans name) or None."""
    stamp = utc_iso(now)
    entry["last_checked_at"] = stamp
    if result.status == harness.SKIPPED:
        entry["status"] = SKIPPED_STATUS
        return None
    if result.status == harness.PASS:
        recovered = entry.get("alert_category") is not None
        previous = entry.get("last_error_category")
        entry.update(status=OK, last_ok_at=stamp, consecutive_failures=0)
        if recovered:
            return {"event": "recovered", "category": previous, "detail": "probe passing again"}
        return None
    category = result.status
    entry.update(
        status=FAILING,
        last_error_at=stamp,
        last_error_category=category,
        last_error_detail=detail,
        consecutive_failures=int(entry.get("consecutive_failures") or 0) + 1,
    )
    open_category = entry.get("alert_category")
    if open_category is None:
        event = "failing"
    elif open_category != category:
        event = "category_changed"
    else:
        last_alert = parse_iso(entry.get("last_alert_at"))
        if last_alert is not None and now - last_alert < realert_after:
            return None
        event = "still_failing"
    return {"event": event, "category": category, "detail": detail}


def run_probe(
    config_path: Path,
    settings_path: Path,
    state_path: Path,
    env: Mapping[str, str],
    sink: Any,
    *,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    probe: Probe = real_probe,
    timeout: float = harness.DEFAULT_TIMEOUT,
    realert_after: timedelta = timedelta(hours=DEFAULT_REALERT_HOURS),
    only: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    enabled = load_enabled(config_path)
    targets = harness.load_targets(config_path, settings_path)
    state, warning = load_state(state_path)
    alerts: list[dict[str, Any]] = []
    for target in targets:
        if only and target.name not in only:
            continue
        if not enabled.get(target.name, True):
            continue
        entry = {**new_entry(), **state["targets"].get(target.name, {})}
        now = now_fn()
        result = probe(target, env, timeout)
        detail = _clean_detail(result.detail, target, env)
        alert = apply_result(entry, result, detail, now, realert_after)
        if alert is not None:
            alert = {"target": target.name, "at": utc_iso(now), **alert}
            if sink.emit(alert):
                entry["alert_category"] = (
                    None if alert["event"] == "recovered" else alert["category"]
                )
                entry["last_alert_at"] = alert["at"]
            alerts.append(alert)
        state["targets"][target.name] = entry
    save_state(state_path, state)
    return state, alerts, warning


# --- operator view -------------------------------------------------------

def build_view(config_path: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for name, is_enabled in load_enabled(config_path).items():
        entry = {**new_entry(), **state["targets"].get(name, {})}
        rows.append({
            "target": name,
            "enabled": is_enabled,
            "status": entry["status"] if is_enabled else DISABLED,
            **{k: entry[k] for k in (
                "last_checked_at", "last_ok_at", "last_error_at",
                "last_error_category", "last_error_detail", "consecutive_failures",
            )},
        })
    return rows


def format_table(rows: list[dict[str, Any]]) -> str:
    cols = [
        ("TARGET", "target"), ("STATUS", "status"), ("LAST OK", "last_ok_at"),
        ("LAST ERROR", "last_error_at"), ("CATEGORY", "last_error_category"),
        ("FAILS", "consecutive_failures"), ("DETAIL", "last_error_detail"),
    ]
    cells = [[head for head, _ in cols]]
    for row in rows:
        cells.append([str(row[key]) if row[key] is not None else "-" for _, key in cols])
    widths = [max(len(line[i]) for line in cells) for i in range(len(cols))]
    return "\n".join(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip()
        for line in cells
    )


def any_failing(rows: list[dict[str, Any]], require_all: bool = False) -> bool:
    bad = {FAILING, SKIPPED_STATUS, "unknown"} if require_all else {FAILING}
    return any(row["enabled"] and row["status"] in bad for row in rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=harness.DEFAULT_CONFIG)
    parser.add_argument("--settings", type=Path, default=harness.DEFAULT_SETTINGS)
    parser.add_argument("--state", type=Path, help=f"state file (default: ${STATE_ENV} or XDG/LOCALAPPDATA state dir)")
    parser.add_argument("--target", action="append", help="limit to named target(s)")
    parser.add_argument("--timeout", type=float, default=harness.DEFAULT_TIMEOUT)
    parser.add_argument("--realert-after", type=float, default=DEFAULT_REALERT_HOURS,
                        metavar="HOURS", help="re-alert on an unchanged failure after this long")
    parser.add_argument("--status", action="store_true", help="print state table; no probing")
    parser.add_argument("--json", action="store_true", help="print state as JSON; no probing")
    parser.add_argument("--require-all", action="store_true",
                        help="treat skipped/never-probed enabled targets as failing")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    sink: Any = None,
    now_fn: Callable[[], datetime] | None = None,
    probe: Probe | None = None,
) -> int:
    args = parse_args(argv)
    env = os.environ if env is None else env
    state_path = args.state or default_state_path(env)
    if _inside_repo(state_path):
        print(f"config error: state file {state_path} is inside the repo tree", file=sys.stderr)
        return 2
    try:
        harness.load_targets(args.config, args.settings)
        load_enabled(args.config)
    except (harness.SmokeConfigError, ValueError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.status or args.json:
        state, warning = load_state(state_path)
        if warning:
            print(f"warning: {warning}", file=sys.stderr)
        rows = build_view(args.config, state)
        print(json.dumps({"state_file": str(state_path), "targets": rows}, indent=2)
              if args.json else format_table(rows))
        return 1 if any_failing(rows, args.require_all) else 0

    try:
        import mcp  # noqa: F401
    except ImportError:
        print("config error: official MCP SDK missing (pip install -r requirements.txt)", file=sys.stderr)
        return 2
    kwargs: dict[str, Any] = {}
    if now_fn:
        kwargs["now_fn"] = now_fn
    if probe:
        kwargs["probe"] = probe
    state, alerts, warning = run_probe(
        args.config, args.settings, state_path, env, sink or build_sink(env),
        timeout=args.timeout, realert_after=timedelta(hours=args.realert_after),
        only=args.target, **kwargs,
    )
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    rows = build_view(args.config, state)
    print(format_table(rows), file=sys.stderr)
    return 1 if any_failing(rows, args.require_all) else 0


if __name__ == "__main__":
    raise SystemExit(main())
