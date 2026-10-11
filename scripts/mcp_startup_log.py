#!/usr/bin/env python3
"""Structured, redacted startup records and bounded phase timeouts for MCP targets.

Stdlib only. One JSON line is emitted per startup phase of a target::

    {"event": "mcp_startup", "ts": "...Z", "target": "PLX-MC-Hub",
     "phase": "discovery", "duration_ms": 41, "outcome": "ok",
     "failure_class": null, "detail": ""}

``phase`` is one of PHASES, ``outcome`` is ``ok`` / ``fail`` / ``timeout`` /
``skipped`` and ``failure_class`` is one of FAILURE_CLASSES (null unless the
outcome is fail or timeout). Records never carry env values, headers, tokens or
command lines; every string is passed through the redactor first.

Sink (``MCP_STARTUP_LOG`` or ``--startup-log``): unset = off, ``-`` or
``stderr`` = stderr, anything else = append to that file path.

Phase timeouts (seconds; env var, then CLI flag on the smoke harness):

  secret_fetch  MCP_STARTUP_TIMEOUT_SECRET_FETCH  --secret-fetch-timeout  10
  child_start   MCP_STARTUP_TIMEOUT_CHILD_START   --child-start-timeout   20
  discovery     MCP_STARTUP_TIMEOUT_DISCOVERY     --discovery-timeout     15
  self_check    MCP_STARTUP_TIMEOUT_SELF_CHECK    --self-check-timeout    15
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SECRET_FETCH = "secret_fetch"
CHILD_START = "child_start"
DISCOVERY = "discovery"
SELF_CHECK = "self_check"
PHASES = (SECRET_FETCH, CHILD_START, DISCOVERY, SELF_CHECK)

TIMEOUT = "timeout"
AUTH = "auth"
SPAWN = "spawn"
PROTOCOL = "protocol"
CONFIG = "config"
UNKNOWN = "unknown"
FAILURE_CLASSES = (TIMEOUT, AUTH, SPAWN, PROTOCOL, CONFIG, UNKNOWN)

OK, FAIL, TIMED_OUT, SKIPPED = "ok", "fail", "timeout", "skipped"

LOG_ENV = "MCP_STARTUP_LOG"
REDACTED = "[REDACTED]"
MAX_DETAIL = 300

DEFAULT_TIMEOUTS = {SECRET_FETCH: 10.0, CHILD_START: 20.0, DISCOVERY: 15.0, SELF_CHECK: 15.0}
TIMEOUT_ENV = {phase: f"MCP_STARTUP_TIMEOUT_{phase.upper()}" for phase in PHASES}

# Shapes that look like credentials even when we do not know the exact value.
_PATTERNS = [
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}"),
    re.compile(r"(?i)\b(authorization|x-api-key|api[_-]?key|token|secret|password|passwd)"
               r"(\"?\s*[:=]\s*\"?)[^\s\"',;&]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
]


def make_redactor(secrets: list[str]) -> Callable[[str], str]:
    """Replace exact secret values, then credential-shaped text, with a marker."""
    values = sorted({s for s in secrets if s}, key=len, reverse=True)

    def redact(text: str) -> str:
        text = str(text)
        for value in values:
            text = text.replace(value, REDACTED)
        text = _PATTERNS[0].sub(lambda m: f"{m.group(1)} {REDACTED}", text)
        text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
        return _PATTERNS[2].sub(REDACTED, text)

    return redact


# --- timeouts ------------------------------------------------------------

@dataclass(frozen=True)
class PhaseTimeouts:
    secret_fetch: float = DEFAULT_TIMEOUTS[SECRET_FETCH]
    child_start: float = DEFAULT_TIMEOUTS[CHILD_START]
    discovery: float = DEFAULT_TIMEOUTS[DISCOVERY]
    self_check: float = DEFAULT_TIMEOUTS[SELF_CHECK]

    def for_phase(self, phase: str) -> float:
        return getattr(self, phase)


def _positive(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number of seconds, got {value!r}") from None
    if number <= 0:
        raise ValueError(f"{label} must be > 0, got {value!r}")
    return number


def resolve_timeouts(
    env: Mapping[str, str], overrides: Mapping[str, float | None] | None = None
) -> PhaseTimeouts:
    """Defaults, then env vars, then explicit (CLI) overrides. Raises ValueError."""
    values = dict(DEFAULT_TIMEOUTS)
    for phase in PHASES:
        raw = env.get(TIMEOUT_ENV[phase])
        if raw not in (None, ""):
            values[phase] = _positive(raw, TIMEOUT_ENV[phase])
    for phase, value in (overrides or {}).items():
        if value is not None:
            values[phase] = _positive(value, f"--{phase.replace('_', '-')}-timeout")
    return PhaseTimeouts(**values)


def timeout_hint(phase: str) -> str:
    flag = f"--{phase.replace('_', '-')}-timeout"
    return f"raise {TIMEOUT_ENV[phase]} or {flag} if the target is just slow"


# --- records -------------------------------------------------------------

class StartupLog:
    """Collects and emits one record per phase for a single target."""

    def __init__(
        self,
        target: str,
        sink: Callable[[str], None] | None = None,
        redact: Callable[[str], str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.target = target
        self.records: list[dict[str, Any]] = []
        self._sink = sink
        self._redact = redact or make_redactor([])
        self._clock = clock
        self._now = now
        self._open: tuple[str, float] | None = None

    @property
    def current_phase(self) -> str | None:
        return self._open[0] if self._open else None

    def add_secrets(self, secrets: list[str]) -> None:
        self._redact = make_redactor(list(secrets))

    def begin(self, phase: str) -> None:
        if phase not in PHASES:
            raise ValueError(f"unknown phase {phase!r}")
        self._open = (phase, self._clock())

    def end(
        self,
        outcome: str = OK,
        failure_class: str | None = None,
        detail: str = "",
        phase: str | None = None,
    ) -> dict[str, Any] | None:
        """Close the open phase (or log ``phase`` with zero duration if none)."""
        if self._open is None and phase is None:
            return None
        name, started = self._open or (phase, self._clock())
        self._open = None
        if outcome in (FAIL, TIMED_OUT):
            failure_class = TIMEOUT if outcome == TIMED_OUT else (failure_class or UNKNOWN)
            if failure_class not in FAILURE_CLASSES:
                failure_class = UNKNOWN
        else:
            failure_class = None
        record = {
            "event": "mcp_startup",
            "ts": self._now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target": self._redact(self.target),
            "phase": name,
            "duration_ms": max(0, round((self._clock() - started) * 1000)),
            "outcome": outcome,
            "failure_class": failure_class,
            "detail": self._redact(detail)[:MAX_DETAIL],
        }
        self.records.append(record)
        if self._sink is not None:
            try:
                self._sink(json.dumps(record, sort_keys=True))
            except Exception:  # logging must never break a probe
                pass
        return record


def make_sink(spec: str | None) -> Callable[[str], None] | None:
    """``None``/empty = off, ``-``/``stderr`` = stderr, else append to a file."""
    if not spec:
        return None
    if spec in ("-", "stderr"):
        return lambda line: print(line, file=sys.stderr, flush=True)

    def write(line: str) -> None:
        with open(spec, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return write


# --- bounded secret fetch ------------------------------------------------

class SecretFetchError(Exception):
    def __init__(self, failure_class: str, detail: str):
        super().__init__(detail)
        self.failure_class = failure_class
        self.detail = detail


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def fetch_secret(command: list[str], timeout: float, env: Mapping[str, str] | None = None) -> str:
    """Run ``command`` (argv list, no shell) and return stripped stdout.

    Bounded by ``timeout``: on expiry the whole process group is killed and
    reaped. Errors carry a class and a fixed message only; the command's argv,
    stdout and stderr never appear in them (they may contain secrets).
    """
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        raise SecretFetchError(CONFIG, "secretFetch.command must be a non-empty list of strings")
    kwargs: dict[str, Any] = {}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=dict(env) if env is not None else None, **kwargs,
        )
    except OSError as exc:
        raise SecretFetchError(SPAWN, f"could not start secret fetch ({type(exc).__name__})") from None
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        proc.communicate()
        raise SecretFetchError(TIMEOUT, f"secret fetch timed out after {timeout:g}s") from None
    except BaseException:
        _kill_group(proc)
        proc.communicate()
        raise
    if proc.returncode != 0:
        raise SecretFetchError(AUTH, f"secret fetch exited with code {proc.returncode}")
    value = out.decode("utf-8", errors="replace").strip()
    if not value:
        raise SecretFetchError(AUTH, "secret fetch returned no value")
    return value
