"""Offline tests for MCP startup records, redaction and bounded phase timeouts.

No network, no real credentials: temp dirs, stub sessions and tiny child
processes only. The ``Sdk*`` tests need the official ``mcp`` package and skip
when it is absent.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_SERVER = REPO_ROOT / "tests" / "fixtures" / "fake_mcp_server.py"
SECRET = "sk-test-startup-secret-98765"
FETCHED = "fetched-planted-credential-4242"


def _load(name):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


su = _load("mcp_startup_log")
harness = _load("smoke_mcp_targets")
HAVE_SDK = importlib.util.find_spec("mcp") is not None


class FakeSession:
    """Stand-in for an MCP ClientSession with per-call delays."""

    def __init__(self, init=0.0, tools=0.0, call=0.0, names=("mc_self_check",),
                 call_result=None):
        self.delays = {"init": init, "tools": tools, "call": call}
        self.names = names
        self.call_result = call_result

    async def initialize(self):
        await asyncio.sleep(self.delays["init"])

    async def list_tools(self):
        await asyncio.sleep(self.delays["tools"])
        return SimpleNamespace(tools=[SimpleNamespace(name=n) for n in self.names])

    async def call_tool(self, name, args):
        await asyncio.sleep(self.delays["call"])
        return self.call_result or SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(text=json.dumps({"data": {"ok": True}}))],
        )


def make_target(**kw):
    return harness.Target(name="fake", transport="stdio", spec={}, **kw)


def run(coro):
    return asyncio.run(coro)


def fast(**kw):
    base = {"secret_fetch": 0.3, "child_start": 0.3, "discovery": 0.3, "self_check": 0.3}
    base.update(kw)
    return su.PhaseTimeouts(**base)


def py_cmd(code):
    return [sys.executable, "-c", code]


class RedactionTests(unittest.TestCase):
    def test_exact_values_and_shapes(self):
        redact = su.make_redactor([SECRET])
        text = (f"key={SECRET} Authorization: Bearer abcdef123456 "
                "x-api-key: zzzz9999 token=hunter2 sk-abcdefghij12")
        out = redact(text)
        for leaked in (SECRET, "abcdef123456", "zzzz9999", "hunter2", "sk-abcdefghij12"):
            self.assertNotIn(leaked, out)
        self.assertIn(su.REDACTED, out)

    def test_longer_secret_wins_over_prefix(self):
        out = su.make_redactor(["abc", "abcdef-long"])("v=abcdef-long")
        self.assertNotIn("def-long", out)

    def test_planted_secret_never_reaches_sink(self):
        lines = []
        log = su.StartupLog("tgt", lines.append, su.make_redactor([SECRET]))
        log.begin(su.DISCOVERY)
        log.end(su.FAIL, su.AUTH, f"server said bad key {SECRET} (Bearer {SECRET})")
        log.end(su.OK, phase=su.SELF_CHECK, detail=SECRET)
        self.assertEqual(len(lines), 2)
        self.assertNotIn(SECRET, "".join(lines))

    def test_secret_in_target_name_is_redacted(self):
        log = su.StartupLog(f"name-{SECRET}", None, su.make_redactor([SECRET]))
        record = log.end(su.OK, phase=su.SELF_CHECK)
        self.assertNotIn(SECRET, json.dumps(record))


class RecordTests(unittest.TestCase):
    def test_schema_duration_and_classes(self):
        ticks = iter([10.0, 10.25, 20.0, 21.5, 30.0, 30.0])
        log = su.StartupLog("t", clock=lambda: next(ticks))
        log.begin(su.CHILD_START)
        ok = log.end(su.OK)
        log.begin(su.DISCOVERY)
        bad = log.end(su.FAIL, "bogus-class", "x")
        log.begin(su.SELF_CHECK)
        slow = log.end(su.TIMED_OUT)
        self.assertEqual(set(ok), {"event", "ts", "target", "phase", "duration_ms",
                                   "outcome", "failure_class", "detail"})
        self.assertEqual((ok["duration_ms"], ok["failure_class"]), (250, None))
        self.assertEqual((bad["duration_ms"], bad["failure_class"]), (1500, su.UNKNOWN))
        self.assertEqual((slow["outcome"], slow["failure_class"]), ("timeout", su.TIMEOUT))
        self.assertTrue(all(r["phase"] in su.PHASES for r in log.records))

    def test_sink_selection_and_file_append(self):
        self.assertIsNone(su.make_sink(None))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "startup.jsonl"
            log = su.StartupLog("t", su.make_sink(str(path)))
            log.end(su.OK, phase=su.SECRET_FETCH)
            log.end(su.OK, phase=su.DISCOVERY)
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual([r["phase"] for r in rows], ["secret_fetch", "discovery"])

    def test_broken_sink_does_not_raise(self):
        def boom(_line):
            raise OSError("disk full")
        su.StartupLog("t", boom).end(su.OK, phase=su.DISCOVERY)


class TimeoutConfigTests(unittest.TestCase):
    def test_defaults_env_flag_precedence(self):
        self.assertEqual(su.resolve_timeouts({}), su.PhaseTimeouts())
        t = su.resolve_timeouts({"MCP_STARTUP_TIMEOUT_DISCOVERY": "7"})
        self.assertEqual(t.discovery, 7.0)
        t = su.resolve_timeouts({"MCP_STARTUP_TIMEOUT_DISCOVERY": "7"}, {"discovery": 2.5})
        self.assertEqual(t.discovery, 2.5)
        self.assertEqual(t.child_start, su.DEFAULT_TIMEOUTS["child_start"])

    def test_invalid_values_rejected(self):
        for env in ({"MCP_STARTUP_TIMEOUT_SELF_CHECK": "abc"},
                    {"MCP_STARTUP_TIMEOUT_SELF_CHECK": "0"},
                    {"MCP_STARTUP_TIMEOUT_SELF_CHECK": "-3"}):
            with self.assertRaises(ValueError):
                su.resolve_timeouts(env)
        with self.assertRaises(ValueError):
            su.resolve_timeouts({}, {"child_start": 0})

    def test_bad_env_is_config_failure_not_crash(self):
        result = run(harness.smoke_target(
            make_target(), {"MCP_STARTUP_TIMEOUT_DISCOVERY": "nope"}, 5))
        self.assertEqual(result.failure_class, su.CONFIG)
        self.assertNotEqual(result.status, harness.PASS)


class SecretFetchTests(unittest.TestCase):
    def test_success_strips_output(self):
        self.assertEqual(su.fetch_secret(py_cmd("print('  v1  ')"), 5), "v1")

    def test_timeout_kills_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pid"
            code = (f"import os,time;open({str(pidfile)!r},'w').write(str(os.getpid()));"
                    "time.sleep(60)")
            started = time.monotonic()
            with self.assertRaises(su.SecretFetchError) as ctx:
                su.fetch_secret(py_cmd(code), 0.5)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(ctx.exception.failure_class, su.TIMEOUT)
            pid = int(pidfile.read_text())
            time.sleep(0.2)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_failure_classes_and_no_leak(self):
        cases = [
            (py_cmd(f"import sys;print({SECRET!r});sys.stderr.write({SECRET!r});sys.exit(4)"), su.AUTH),
            (py_cmd("pass"), su.AUTH),
            (["/nonexistent/secret-helper", SECRET], su.SPAWN),
            ([], su.CONFIG),
            ("not-a-list", su.CONFIG),
        ]
        for command, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(su.SecretFetchError) as ctx:
                    su.fetch_secret(command, 5)
                self.assertEqual(ctx.exception.failure_class, expected)
                self.assertNotIn(SECRET, ctx.exception.detail)


class PhaseTimeoutTests(unittest.TestCase):
    def _phase_run(self, session, timeouts):
        log = su.StartupLog("fake")
        log.begin(su.CHILD_START)
        with self.assertRaises(harness._SmokeFailure) as ctx:
            run(harness._session_checks(session, make_target(), None, log, timeouts))
        return ctx.exception, log

    def test_child_start_timeout(self):
        failure, log = self._phase_run(FakeSession(init=5), fast(child_start=0.1))
        self.assertEqual(failure.failure_class, su.TIMEOUT)
        self.assertEqual(log.current_phase, su.CHILD_START)
        self.assertIn("child_start timed out", failure.detail)
        self.assertIn("MCP_STARTUP_TIMEOUT_CHILD_START", failure.detail)

    def test_discovery_timeout(self):
        failure, log = self._phase_run(FakeSession(tools=5), fast(discovery=0.1))
        self.assertEqual(failure.failure_class, su.TIMEOUT)
        self.assertEqual(log.current_phase, su.DISCOVERY)
        self.assertEqual([r["phase"] for r in log.records], [su.CHILD_START])

    def test_self_check_timeout(self):
        failure, log = self._phase_run(FakeSession(call=5), fast(self_check=0.1))
        self.assertEqual(failure.failure_class, su.TIMEOUT)
        self.assertEqual(log.current_phase, su.SELF_CHECK)
        self.assertEqual([r["phase"] for r in log.records], [su.CHILD_START, su.DISCOVERY])

    def test_secret_fetch_timeout_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "log.jsonl"
            target = make_target(
                required_env=["FAKE_KEY"],
                secret_fetch={"env": "FAKE_KEY", "command": py_cmd("import time;time.sleep(60)")},
            )
            env = {"MCP_STARTUP_TIMEOUT_SECRET_FETCH": "0.4", "MCP_STARTUP_LOG": str(sink)}
            started = time.monotonic()
            result = run(harness.smoke_target(target, env, 30))
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual((result.status, result.failure_class, result.phase),
                             (harness.STARTUP, su.TIMEOUT, su.SECRET_FETCH))
            self.assertIn("MCP_STARTUP_TIMEOUT_SECRET_FETCH", result.detail)
            self.assertIn("timed out", harness.format_result(result))
            rows = [json.loads(x) for x in sink.read_text().splitlines()]
            self.assertEqual([(r["phase"], r["outcome"], r["failure_class"]) for r in rows],
                             [("secret_fetch", "timeout", "timeout")])

    def test_overall_timeout_attributed_to_open_phase(self):
        async def slow_child(target, env, errlog, log=None, timeouts=None):
            log.begin(su.CHILD_START)
            await asyncio.sleep(30)

        log = su.StartupLog("fake")
        with mock.patch.object(harness, "_run_target", slow_child):
            result = run(harness.smoke_target(make_target(), {}, 0.2, fast(), log))
        self.assertEqual((result.status, result.failure_class), (harness.STARTUP, su.TIMEOUT))
        self.assertEqual(log.records[-1]["phase"], su.CHILD_START)
        self.assertEqual(log.records[-1]["outcome"], "timeout")


class SmokeTargetLoggingTests(unittest.TestCase):
    def _smoke(self, session, target=None, env=None, timeouts=None):
        async def fake_run(tgt, environ, errlog, log=None, timeouts=None):
            log.begin(su.CHILD_START)
            await harness._session_checks(session, tgt, None, log, timeouts)

        log = su.StartupLog("fake")
        with mock.patch.object(harness, "_run_target", fake_run):
            result = run(harness.smoke_target(target or make_target(), env or {}, 5,
                                              timeouts or fast(), log))
        return result, log

    def test_success_records_each_phase_with_duration(self):
        session = FakeSession(init=0.05, tools=0.05, call=0.05)
        result, log = self._smoke(session)
        self.assertEqual(result.status, harness.PASS)
        self.assertEqual([r["phase"] for r in log.records],
                         [su.CHILD_START, su.DISCOVERY, su.SELF_CHECK])
        for record in log.records:
            self.assertEqual(record["outcome"], "ok")
            self.assertIsNone(record["failure_class"])
            self.assertGreaterEqual(record["duration_ms"], 40)

    def test_auth_failure_class(self):
        bad = SimpleNamespace(isError=True, content=[SimpleNamespace(text="denied")])
        result, log = self._smoke(FakeSession(call_result=bad))
        self.assertEqual((result.status, result.failure_class), (harness.AUTH, su.AUTH))
        self.assertEqual(log.records[-1]["phase"], su.SELF_CHECK)
        self.assertEqual(log.records[-1]["failure_class"], su.AUTH)

    def test_missing_tools_is_config_class_in_discovery(self):
        result, log = self._smoke(FakeSession(names=("other",)))
        self.assertEqual((result.status, result.failure_class), (harness.DISCOVERY, su.CONFIG))
        self.assertEqual((log.records[-1]["phase"], log.records[-1]["outcome"]),
                         (su.DISCOVERY, "fail"))

    def test_empty_self_check_is_protocol_class(self):
        empty = SimpleNamespace(isError=False, content=[])
        result, _log = self._smoke(FakeSession(call_result=empty))
        self.assertEqual((result.status, result.failure_class), (harness.PROTOCOL, su.PROTOCOL))

    def test_unexpected_error_is_unknown_class(self):
        class Boom(FakeSession):
            async def list_tools(self):
                raise RuntimeError("weird")
        result, log = self._smoke(Boom())
        self.assertIn(result.failure_class, (su.UNKNOWN, su.SPAWN))
        self.assertEqual(log.records[-1]["phase"], su.DISCOVERY)

    def test_missing_secret_helper_is_spawn_class(self):
        target = make_target(
            required_env=["K"], secret_fetch={"env": "K", "command": ["/nonexistent/helper"]})
        result, log = self._smoke(FakeSession(), target)
        self.assertEqual((result.failure_class, result.phase), (su.SPAWN, su.SECRET_FETCH))
        self.assertEqual(log.records[0]["failure_class"], su.SPAWN)

    def test_no_credential_logs_skipped(self):
        target = make_target(required_env=["NOPE"])
        result, log = self._smoke(FakeSession(), target)
        self.assertEqual(result.status, harness.SKIPPED)
        self.assertEqual((log.records[0]["phase"], log.records[0]["outcome"]),
                         (su.SECRET_FETCH, "skipped"))

    def test_fetched_secret_never_logged_or_in_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "log.jsonl"
            leaky = SimpleNamespace(
                isError=True, content=[SimpleNamespace(text=f"bad key {FETCHED}")])
            target = make_target(
                required_env=["K"],
                secret_fetch={"env": "K", "command": py_cmd(f"print({FETCHED!r})")})
            async def fake_run(tgt, environ, errlog, log=None, timeouts=None):
                self.assertEqual(environ["K"], FETCHED)
                log.begin(su.CHILD_START)
                await harness._session_checks(FakeSession(call_result=leaky), tgt, None, log, timeouts)
            with mock.patch.object(harness, "_run_target", fake_run):
                result = run(harness.smoke_target(
                    target, {"MCP_STARTUP_LOG": str(sink), "SOME_ENV": SECRET}, 5, fast()))
            written = sink.read_text()
            self.assertEqual(result.status, harness.AUTH)
            self.assertNotIn(FETCHED, written + result.detail)
            self.assertIn(su.REDACTED, written)
            phases = [json.loads(x)["phase"] for x in written.splitlines()]
            self.assertEqual(phases, ["secret_fetch", "child_start", "discovery", "self_check"])

    def test_no_log_output_by_default(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            async def fake_run(*a, **k):
                return None
            with mock.patch.object(harness, "_run_target", fake_run):
                run(harness.smoke_target(make_target(), {}, 5))
        self.assertEqual(err.getvalue(), "")


@unittest.skipUnless(HAVE_SDK, "official mcp SDK not installed")
class SdkStartupTests(unittest.TestCase):
    def _main(self, mode, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            config = {"mcpServers": {"fake": {
                "command": sys.executable, "args": [str(FAKE_SERVER)],
                "env": {"FAKE_MCP_MODE": mode, "FAKE_MCP_KEY": SECRET,
                        "FAKE_MCP_PRESENTED": "${FAKE_SMOKE_KEY}"}}}}
            (tmp / "mcp.json").write_text(json.dumps(config))
            sink = tmp / "log.jsonl"
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = harness.main(
                    ["--config", str(tmp / "mcp.json"), "--settings", str(tmp / "s.json"),
                     "--startup-log", str(sink), *extra],
                    env={"FAKE_SMOKE_KEY": SECRET})
            rows = [json.loads(x) for x in sink.read_text().splitlines()] if sink.exists() else []
            return code, out.getvalue(), rows

    def test_hung_child_times_out_in_child_start(self):
        code, out, rows = self._main("hang", "--child-start-timeout", "1")
        self.assertEqual(code, 1)
        self.assertIn("child_start timed out", out)
        self.assertEqual((rows[-1]["phase"], rows[-1]["failure_class"]), ("child_start", "timeout"))
        self.assertNotIn(SECRET, out + json.dumps(rows))

    def test_ok_run_logs_all_phases(self):
        code, out, rows = self._main("ok")
        self.assertEqual(code, 0, out)
        self.assertEqual([r["phase"] for r in rows],
                         ["secret_fetch", "child_start", "discovery", "self_check"])
        self.assertNotIn(SECRET, json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
