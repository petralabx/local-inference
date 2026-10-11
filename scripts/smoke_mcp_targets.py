#!/usr/bin/env python3
"""Protocol smoke test for every MCP target this repo configures.

For each server in ``.mcp.json`` the harness connects (stdio subprocess or
streamable HTTP), initializes an official MCP SDK client session, runs
``list_tools`` against the expected tool set and calls the authenticated
self-check tool. Failures carry one distinct category:

  STARTUP    process did not spawn or exit cleanly, endpoint unreachable,
             or initialize timed out
  PROTOCOL   server answered with something that is not valid MCP
  DISCOVERY  list_tools worked but expected tools are missing
  AUTH       credential rejected (HTTP 401/403 or self-check error)

Credentials come only from the environment at run time and are redacted from
all output. A target whose credential is unset is reported
``SKIPPED (no credential)``; ``--require-all`` turns that into a failure.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / ".mcp.json"
DEFAULT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SELF_CHECK_TOOL = "mc_self_check"
DEFAULT_TIMEOUT = 30.0

def _load_sibling(name: str):
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


startup = _load_sibling("mcp_startup_log")

STARTUP = "STARTUP"
PROTOCOL = "PROTOCOL"
DISCOVERY = "DISCOVERY"
AUTH = "AUTH"
PASS = "PASS"
SKIPPED = "SKIPPED"

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
REDACTED = "[REDACTED]"


class SmokeConfigError(RuntimeError):
    """Raised when the MCP config cannot be read."""


@dataclass
class Target:
    name: str
    transport: str  # "stdio" or "http"
    spec: dict[str, Any]
    required_env: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    self_check_tool: str = SELF_CHECK_TOOL
    # Optional ``smoke.secretFetch`` {"env": VAR, "command": [argv...]}: run
    # (bounded) to obtain VAR when it is not already set in the environment.
    secret_fetch: dict[str, Any] | None = None


@dataclass
class Result:
    name: str
    status: str  # PASS, SKIPPED or a failure category
    detail: str = ""
    failure_class: str | None = None  # mcp_startup_log.FAILURE_CLASSES
    phase: str | None = None  # startup phase that failed


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def referenced_required_vars(spec: Mapping[str, Any]) -> list[str]:
    """Env vars referenced as ``${VAR}`` (no default); these are credentials."""
    names: list[str] = []
    for text in _walk_strings(spec):
        for match in _PLACEHOLDER.finditer(text):
            if match.group(2) is None and match.group(1) not in names:
                names.append(match.group(1))
    return names


def expand(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return _PLACEHOLDER.sub(
            lambda m: env.get(m.group(1)) or (m.group(2) or ""), value
        )
    if isinstance(value, Mapping):
        return {k: expand(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v, env) for v in value]
    return value


def _expected_tools(settings_path: Path, name: str) -> list[str]:
    if not settings_path.exists():
        return []
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SmokeConfigError(f"cannot read {settings_path}: {exc}") from exc
    prefix = f"mcp__{name}__"
    perms = data.get("permissions", {})
    tools: list[str] = []
    for key in ("allow", "ask"):
        for entry in perms.get(key, []):
            if entry.startswith(prefix) and entry[len(prefix):] not in tools:
                tools.append(entry[len(prefix):])
    return tools


def load_targets(config_path: Path, settings_path: Path) -> list[Target]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SmokeConfigError(f"cannot read {config_path}: {exc}") from exc
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise SmokeConfigError(f"no mcpServers in {config_path}")
    targets = []
    for name, spec in servers.items():
        if spec.get("command"):
            transport = "stdio"
        elif spec.get("url"):
            transport = "http"
        else:
            raise SmokeConfigError(f"{name}: needs 'command' or 'url'")
        expected = _expected_tools(settings_path, name)
        smoke = spec.get("smoke", {}) if isinstance(spec.get("smoke"), dict) else {}
        expected = smoke.get("expectedTools", expected)
        targets.append(
            Target(
                name=name,
                transport=transport,
                spec={k: v for k, v in spec.items() if k != "smoke"},
                required_env=referenced_required_vars(spec),
                expected_tools=list(expected),
                self_check_tool=smoke.get("selfCheckTool", SELF_CHECK_TOOL),
                secret_fetch=smoke.get("secretFetch")
                if isinstance(smoke.get("secretFetch"), dict) else None,
            )
        )
    return targets


def make_redactor(secrets: list[str]):
    values = sorted({s for s in secrets if s}, key=len, reverse=True)

    def redact(text: str) -> str:
        for value in values:
            text = text.replace(value, REDACTED)
        return text

    return redact


_CLASS_FOR_CATEGORY = {
    STARTUP: startup.SPAWN,
    PROTOCOL: startup.PROTOCOL,
    DISCOVERY: startup.CONFIG,
    AUTH: startup.AUTH,
}


def _flatten(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            yield from _flatten(sub)
    else:
        yield exc


class _SmokeFailure(Exception):
    def __init__(self, category: str, detail: str, failure_class: str | None = None):
        super().__init__(detail)
        self.category = category
        self.detail = detail
        self.failure_class = failure_class or _CLASS_FOR_CATEGORY.get(
            category, startup.UNKNOWN
        )


def _phase_timeout(phase: str, seconds: float) -> _SmokeFailure:
    return _SmokeFailure(
        STARTUP,
        f"{phase} timed out after {seconds:g}s ({startup.timeout_hint(phase)})",
        startup.TIMEOUT,
    )


async def _bounded(coro: Any, phase: str, timeouts: Any) -> Any:
    """Await ``coro`` for at most the phase timeout; cancelling it on expiry."""
    if timeouts is None:
        return await coro
    seconds = timeouts.for_phase(phase)
    try:
        return await asyncio.wait_for(coro, seconds)
    except TimeoutError:
        raise _phase_timeout(phase, seconds) from None


def _classify_stage_error(exc: BaseException, stage: str) -> _SmokeFailure:
    """Map an SDK/transport exception raised during ``stage`` to a category."""
    leaves = list(_flatten(exc))
    for leaf in leaves:
        if isinstance(leaf, _SmokeFailure):
            return leaf
    import httpx
    from mcp.shared.exceptions import McpError
    from pydantic import ValidationError

    for leaf in leaves:
        if isinstance(leaf, httpx.HTTPStatusError):
            code = leaf.response.status_code
            if code in (401, 403):
                return _SmokeFailure(AUTH, f"{stage}: HTTP {code} from server")
            return _SmokeFailure(STARTUP, f"{stage}: HTTP {code} from server")
    for leaf in leaves:
        if isinstance(leaf, (ValidationError, json.JSONDecodeError)):
            return _SmokeFailure(PROTOCOL, f"{stage}: invalid MCP response: {leaf}")
    for leaf in leaves:
        if isinstance(leaf, McpError):
            message = str(leaf)
            if "closed" in message.lower() or "timed out" in message.lower():
                return _SmokeFailure(STARTUP, f"{stage}: {message}")
            return _SmokeFailure(PROTOCOL, f"{stage}: {message}")
    leaf = leaves[0]
    return _SmokeFailure(STARTUP, f"{stage}: {type(leaf).__name__}: {leaf}")


def _check_self_check(target: Target, result: Any, header_repo: str | None) -> None:
    if result.isError:
        text = " ".join(
            getattr(c, "text", "") for c in result.content if getattr(c, "text", "")
        )
        raise _SmokeFailure(AUTH, f"{target.self_check_tool} returned error: {text[:300]}")
    texts = [c.text for c in result.content if getattr(c, "text", None)]
    if not texts:
        raise _SmokeFailure(PROTOCOL, f"{target.self_check_tool} returned no text content")
    try:
        payload = json.loads(texts[0])
    except ValueError:
        return  # opaque but successful self-check
    if not isinstance(payload, dict):
        return
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if data.get("ok") is False:
        raise _SmokeFailure(AUTH, f"{target.self_check_tool} reported ok=false")
    actor = (payload.get("meta") or {}).get("actor") or {}
    if header_repo and actor.get("repo") and actor["repo"] != header_repo:
        raise _SmokeFailure(
            AUTH,
            f"{target.self_check_tool} actor.repo {actor['repo']!r} != {header_repo!r}",
        )


async def _session_checks(
    session: Any,
    target: Target,
    header_repo: str | None,
    log: Any = None,
    timeouts: Any = None,
) -> None:
    """Run initialize, discovery and self-check; each phase is bounded and logged.

    ``child_start`` is opened by the caller (before the child is spawned) and
    closed here once ``initialize`` answers. A phase left open on error is
    closed by the caller with the failure's class.
    """
    try:
        await _bounded(session.initialize(), startup.CHILD_START, timeouts)
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "initialize") from None
    if log is not None:
        log.end(startup.OK)
        log.begin(startup.DISCOVERY)
    try:
        listed = await _bounded(session.list_tools(), startup.DISCOVERY, timeouts)
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "list_tools") from None
    names = {tool.name for tool in listed.tools}
    needed = list(target.expected_tools)
    if target.self_check_tool not in needed:
        needed.append(target.self_check_tool)
    missing = [n for n in needed if n not in names]
    if missing:
        raise _SmokeFailure(DISCOVERY, f"missing tools: {', '.join(missing)}")
    if log is not None:
        log.end(startup.OK)
        log.begin(startup.SELF_CHECK)
    try:
        result = await _bounded(
            session.call_tool(target.self_check_tool, {}), startup.SELF_CHECK, timeouts
        )
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, target.self_check_tool) from None
    _check_self_check(target, result, header_repo)
    if log is not None:
        log.end(startup.OK)


async def _run_target(
    target: Target,
    env: Mapping[str, str],
    errlog: Any,
    log: Any = None,
    timeouts: Any = None,
) -> None:
    import httpx
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    spec = expand(target.spec, env)
    header_repo = (spec.get("headers") or {}).get("x-mc-repo")
    if log is not None:
        log.begin(startup.CHILD_START)
    try:
        if target.transport == "stdio":
            params = StdioServerParameters(
                command=spec["command"],
                args=spec.get("args", []),
                env=spec.get("env") or None,
                cwd=spec.get("cwd"),
            )
            transport = stdio_client(params, errlog=errlog)
            http_client = None
        else:
            http_client = httpx.AsyncClient(
                headers=spec.get("headers") or None, timeout=30.0, follow_redirects=True
            )
            transport = streamable_http_client(spec["url"], http_client=http_client)
        try:
            async with transport as streams, ClientSession(streams[0], streams[1]) as session:
                await _session_checks(session, target, header_repo, log, timeouts)
        finally:
            if http_client is not None:
                await http_client.aclose()
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "connect") from None


def _fetch_target_secret(
    target: Target, env: Mapping[str, str], timeouts: Any, log: Any
) -> dict[str, str] | Result:
    """Resolve ``smoke.secretFetch`` (bounded). Returns env additions or a failed Result."""
    spec = target.secret_fetch
    if not spec:
        return {}
    var = spec.get("env")
    if not isinstance(var, str) or not var:
        return {}
    if env.get(var):
        return {}  # already provided by the environment; nothing to fetch
    log.begin(startup.SECRET_FETCH)
    try:
        value = startup.fetch_secret(
            spec.get("command"), timeouts.secret_fetch, env=dict(env)
        )
    except startup.SecretFetchError as err:
        log.end(
            startup.TIMED_OUT if err.failure_class == startup.TIMEOUT else startup.FAIL,
            err.failure_class,
            err.detail,
        )
        detail = err.detail
        if err.failure_class == startup.TIMEOUT:
            detail += f" ({startup.timeout_hint(startup.SECRET_FETCH)})"
        return Result(
            target.name, STARTUP if err.failure_class != startup.AUTH else AUTH,
            detail, err.failure_class, startup.SECRET_FETCH,
        )
    log.add_secrets([value])
    log.end(startup.OK)
    return {var: value}


async def smoke_target(
    target: Target,
    env: Mapping[str, str],
    timeout: float,
    timeouts: Any = None,
    log: Any = None,
) -> Result:
    """Smoke one target. ``timeout`` caps the whole run; ``timeouts`` bounds each phase.

    One startup record per phase goes to ``log`` (default: sink from
    ``MCP_STARTUP_LOG`` in ``env``; off when unset).
    """
    try:
        timeouts = timeouts or startup.resolve_timeouts(env)
    except ValueError as exc:
        return Result(target.name, STARTUP, f"config error: {exc}", startup.CONFIG)
    if log is None:
        log = startup.StartupLog(target.name, startup.make_sink(env.get(startup.LOG_ENV)))
    env = dict(env)
    fetched = _fetch_target_secret(target, env, timeouts, log)
    if isinstance(fetched, Result):
        return fetched
    env.update(fetched)
    fetched_now = bool(fetched)
    missing = [name for name in target.required_env if not env.get(name)]
    if missing:
        log.end(startup.SKIPPED, detail="no credential", phase=startup.SECRET_FETCH)
        return Result(target.name, SKIPPED, "no credential")
    secrets = [env[name] for name in target.required_env]
    redact = make_redactor(secrets)
    log.add_secrets(secrets)
    if target.required_env and not fetched_now:
        log.end(startup.OK, phase=startup.SECRET_FETCH)  # credential came from env
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as errlog:
        try:
            await asyncio.wait_for(
                _run_target(target, env, errlog, log, timeouts), timeout
            )
        except TimeoutError:
            phase = log.current_phase or startup.CHILD_START
            log.end(startup.TIMED_OUT, detail=f"overall timeout {timeout:g}s", phase=phase)
            return Result(
                target.name, STARTUP,
                f"timed out after {timeout:g}s in {phase} "
                f"(raise --timeout or {startup.timeout_hint(phase)})",
                startup.TIMEOUT, phase,
            )
        except _SmokeFailure as failure:
            phase = log.current_phase
            log.end(
                startup.TIMED_OUT if failure.failure_class == startup.TIMEOUT else startup.FAIL,
                failure.failure_class,
                failure.detail,
            )
            detail = failure.detail
            if failure.category == STARTUP and failure.failure_class != startup.TIMEOUT:
                errlog.seek(0)
                tail = errlog.read()[-300:].strip()
                if tail:
                    detail += f" | server stderr: {tail}"
            return Result(
                target.name, failure.category, redact(detail), failure.failure_class, phase
            )
        except Exception as exc:  # noqa: BLE001 -- classify unexpected harness/SDK errors
            phase = log.current_phase
            log.end(startup.FAIL, startup.UNKNOWN, f"unexpected {type(exc).__name__}")
            return Result(
                target.name, PROTOCOL, redact(f"unexpected {type(exc).__name__}: {exc}"),
                startup.UNKNOWN, phase,
            )
    return Result(target.name, PASS, f"{len(target.expected_tools)} expected tools present")


def format_result(result: Result) -> str:
    if result.status == SKIPPED:
        return f"{result.name}: SKIPPED (no credential)"
    if result.status == PASS:
        return f"{result.name}: PASS - {result.detail}"
    return f"{result.name}: FAIL [{result.status}] {result.detail}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--target", action="append", help="limit to named target(s)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="overall cap per target (seconds)")
    for phase in startup.PHASES:
        parser.add_argument(
            f"--{phase.replace('_', '-')}-timeout", dest=f"{phase}_timeout",
            type=float, metavar="SECONDS",
            help=f"{phase} bound (default {startup.DEFAULT_TIMEOUTS[phase]:g}, "
                 f"env {startup.TIMEOUT_ENV[phase]})",
        )
    parser.add_argument(
        "--startup-log", metavar="PATH",
        help=f"append JSON startup records to PATH ('-' = stderr; env {startup.LOG_ENV})",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="treat SKIPPED (no credential) as a failure",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = parse_args(argv)
    env = os.environ if env is None else env
    try:
        targets = load_targets(args.config, args.settings)
    except SmokeConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    if args.target:
        unknown = set(args.target) - {t.name for t in targets}
        if unknown:
            print(f"unknown target(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        targets = [t for t in targets if t.name in args.target]
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("config error: official MCP SDK missing (pip install -r requirements.txt)", file=sys.stderr)
        return 2

    try:
        timeouts = startup.resolve_timeouts(
            env, {p: getattr(args, f"{p}_timeout") for p in startup.PHASES}
        )
    except ValueError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    sink = startup.make_sink(args.startup_log or env.get(startup.LOG_ENV))
    results = [
        asyncio.run(smoke_target(
            t, env, args.timeout, timeouts, startup.StartupLog(t.name, sink)
        ))
        for t in targets
    ]
    for result in results:
        print(format_result(result))
    failed = [r for r in results if r.status not in (PASS, SKIPPED)]
    skipped = [r for r in results if r.status == SKIPPED]
    print(
        f"summary: {len(results) - len(failed) - len(skipped)} passed, "
        f"{len(failed)} failed, {len(skipped)} skipped"
    )
    if failed:
        return 1
    if skipped and args.require_all:
        print("--require-all: skipped targets count as failure", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
