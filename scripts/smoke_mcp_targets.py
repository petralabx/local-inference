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

# Load beside this script even when imported by file path from offline tests.
_root_spec = importlib.util.spec_from_file_location(
    "mcp_roots", Path(__file__).resolve().with_name("mcp_roots.py")
)
roots = importlib.util.module_from_spec(_root_spec)
sys.modules["mcp_roots"] = roots
_root_spec.loader.exec_module(roots)

REPO_ROOT = roots.SCRIPT_ROOT
DEFAULT_CONFIG = REPO_ROOT / ".mcp.json"
DEFAULT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SELF_CHECK_TOOL = "mc_self_check"
DEFAULT_TIMEOUT = 30.0

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


@dataclass
class Result:
    name: str
    status: str  # PASS, SKIPPED or a failure category
    detail: str = ""


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


def _flatten(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            yield from _flatten(sub)
    else:
        yield exc


class _SmokeFailure(Exception):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


def _classify_stage_error(exc: BaseException, stage: str) -> _SmokeFailure:
    """Map an SDK/transport exception raised during ``stage`` to a category."""
    import httpx
    from mcp.shared.exceptions import McpError
    from pydantic import ValidationError

    leaves = list(_flatten(exc))
    for leaf in leaves:
        if isinstance(leaf, _SmokeFailure):
            return leaf
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


async def _session_checks(session: Any, target: Target, header_repo: str | None) -> None:
    try:
        await session.initialize()
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "initialize") from None
    try:
        listed = await session.list_tools()
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "list_tools") from None
    names = {tool.name for tool in listed.tools}
    needed = list(target.expected_tools)
    if target.self_check_tool not in needed:
        needed.append(target.self_check_tool)
    missing = [n for n in needed if n not in names]
    if missing:
        raise _SmokeFailure(DISCOVERY, f"missing tools: {', '.join(missing)}")
    try:
        result = await session.call_tool(target.self_check_tool, {})
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, target.self_check_tool) from None
    _check_self_check(target, result, header_repo)


async def _run_target(target: Target, env: Mapping[str, str], errlog: Any) -> None:
    import httpx
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    spec = expand(target.spec, env)
    header_repo = (spec.get("headers") or {}).get("x-mc-repo")
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
                await _session_checks(session, target, header_repo)
        finally:
            if http_client is not None:
                await http_client.aclose()
    except Exception as exc:  # noqa: BLE001 -- SDK failures must retain their stage category
        raise _classify_stage_error(exc, "connect") from None


async def smoke_target(
    target: Target, env: Mapping[str, str], timeout: float
) -> Result:
    missing = [name for name in target.required_env if not env.get(name)]
    if missing:
        return Result(target.name, SKIPPED, "no credential")
    secrets = [env[name] for name in target.required_env]
    redact = make_redactor(secrets)
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as errlog:
        try:
            await asyncio.wait_for(_run_target(target, env, errlog), timeout)
        except TimeoutError:
            return Result(target.name, STARTUP, f"timed out after {timeout:g}s")
        except _SmokeFailure as failure:
            detail = failure.detail
            if failure.category == STARTUP:
                errlog.seek(0)
                tail = errlog.read()[-300:].strip()
                if tail:
                    detail += f" | server stderr: {tail}"
            return Result(target.name, failure.category, redact(detail))
        except Exception as exc:  # noqa: BLE001 -- classify unexpected harness/SDK errors
            return Result(
                target.name, PROTOCOL, redact(f"unexpected {type(exc).__name__}: {exc}")
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
    roots.add_source_args(parser)
    parser.add_argument("--target", action="append", help="limit to named target(s)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
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
        sources = roots.resolve_sources(args.root, args.config, args.settings, env=env)
        targets = load_targets(sources.config, sources.settings)
    except (SmokeConfigError, roots.RootError) as exc:
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

    results = [
        asyncio.run(smoke_target(t, env, args.timeout)) for t in targets
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
