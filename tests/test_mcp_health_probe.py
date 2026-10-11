"""Offline tests for scripts/mcp_health_probe.py (fake MCP server, fake clock, fake sink)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_SERVER = REPO_ROOT / "tests" / "fixtures" / "fake_mcp_server.py"
SECRET = "sk-test-health-secret-98765"


def _load():
    path = REPO_ROOT / "scripts" / "mcp_health_probe.py"
    spec = importlib.util.spec_from_file_location("mcp_health_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_health_probe"] = module
    spec.loader.exec_module(module)
    return module


probe_mod = _load()
harness = probe_mod.harness


class FakeSink:
    def __init__(self, ok=True):
        self.alerts = []
        self.ok = ok

    def emit(self, alert):
        self.alerts.append(alert)
        return self.ok


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


class HealthProbeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.state = self.tmp / "state" / "health.json"
        self.sink = FakeSink()
        self.clock = FakeClock()
        self.env = {"FAKE_SMOKE_KEY": SECRET}
        (self.tmp / "settings.json").write_text(json.dumps(
            {"permissions": {"allow": ["mcp__fake__mc_self_check", "mcp__fake__mc_get_context"]}}
        ))

    def _config(self, mode="ok", extra=None):
        fake = {
            "command": sys.executable,
            "args": [str(FAKE_SERVER)],
            "env": {"FAKE_MCP_MODE": mode, "FAKE_MCP_KEY": SECRET,
                    "FAKE_MCP_PRESENTED": "${FAKE_SMOKE_KEY}"},
        }
        servers = {"fake": fake, **(extra or {})}
        (self.tmp / "mcp.json").write_text(json.dumps({"mcpServers": servers}))

    def _run(self, mode="ok", **kw):
        self._config(mode, kw.pop("extra", None))
        return probe_mod.run_probe(
            self.tmp / "mcp.json", self.tmp / "settings.json", self.state,
            kw.pop("env", self.env), self.sink,
            now_fn=self.clock, timeout=5, **kw,
        )

    def _entry(self, name="fake"):
        return json.loads(self.state.read_text())["targets"][name]

    def _cli(self, *args, mode=None):
        if mode:
            self._config(mode)
        argv = ["--config", str(self.tmp / "mcp.json"), "--settings", str(self.tmp / "settings.json"),
                "--state", str(self.state), *args]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = probe_mod.main(argv, env=self.env, sink=self.sink, now_fn=self.clock)
        return code, out.getvalue(), err.getvalue()

    def test_happy_path_updates_last_ok(self):
        self._run()
        entry = self._entry()
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["last_ok_at"], "2026-10-11T12:00:00Z")
        self.assertEqual(entry["last_checked_at"], "2026-10-11T12:00:00Z")
        self.assertEqual(entry["consecutive_failures"], 0)
        self.assertIsNone(entry["last_error_category"])
        self.assertEqual(self.sink.alerts, [])

    def test_failure_sets_last_error_and_category(self):
        self._run()
        self.clock.advance(minutes=15)
        self._run(mode="missing_tool")
        entry = self._entry()
        self.assertEqual(entry["status"], "failing")
        self.assertEqual(entry["last_error_category"], "DISCOVERY")
        self.assertEqual(entry["last_error_at"], "2026-10-11T12:15:00Z")
        self.assertEqual(entry["last_ok_at"], "2026-10-11T12:00:00Z")
        self.assertIn("mc_get_context", entry["last_error_detail"])
        self.assertEqual(entry["consecutive_failures"], 1)
        self.assertEqual([a["event"] for a in self.sink.alerts], ["failing"])

    def test_dedup_repeat_failure_alerts_once_and_recovery_once(self):
        for _ in range(3):
            self._run(mode="missing_tool")
            self.clock.advance(minutes=15)
        self.assertEqual([a["event"] for a in self.sink.alerts], ["failing"])
        self.assertEqual(self._entry()["consecutive_failures"], 3)
        self._run(mode="ok")
        self._run(mode="ok")
        self.assertEqual([a["event"] for a in self.sink.alerts], ["failing", "recovered"])
        self.assertEqual(self._entry()["consecutive_failures"], 0)

    def test_category_change_realerts(self):
        self._run(mode="missing_tool")
        self.clock.advance(minutes=15)
        self._run(mode="auth_reject")
        self.assertEqual([(a["event"], a["category"]) for a in self.sink.alerts],
                         [("failing", "DISCOVERY"), ("category_changed", "AUTH")])

    def test_realert_after_window(self):
        self._run(mode="missing_tool")
        self.clock.advance(hours=5, minutes=59)
        self._run(mode="missing_tool")
        self.assertEqual(len(self.sink.alerts), 1)
        self.clock.advance(minutes=2)
        self._run(mode="missing_tool")
        self.assertEqual([a["event"] for a in self.sink.alerts], ["failing", "still_failing"])

    def test_failed_sink_does_not_consume_alert(self):
        self.sink.ok = False
        self._run(mode="missing_tool")
        self._run(mode="missing_tool")
        self.assertEqual(len(self.sink.alerts), 2)  # retried because delivery failed
        self.sink.ok = True
        self._run(mode="missing_tool")
        self._run(mode="missing_tool")
        self.assertEqual(len(self.sink.alerts), 3)

    def test_disabled_target_is_skipped(self):
        calls = []

        def spy(target, env, timeout):
            calls.append(target.name)
            return harness.Result(target.name, harness.PASS, "")

        extra = {"off": {"command": "/nonexistent", "smoke": {"enabled": False}}}
        self._config("ok", extra)
        probe_mod.run_probe(self.tmp / "mcp.json", self.tmp / "settings.json", self.state,
                            self.env, self.sink, now_fn=self.clock, probe=spy)
        self.assertEqual(calls, ["fake"])
        self.assertNotIn("off", json.loads(self.state.read_text())["targets"])
        self.assertEqual(self.sink.alerts, [])
        rows = probe_mod.build_view(self.tmp / "mcp.json", json.loads(self.state.read_text()))
        self.assertEqual({r["target"]: r["status"] for r in rows}, {"fake": "ok", "off": "disabled"})

    def test_enabled_defaults_true(self):
        self._config("ok")
        self.assertEqual(probe_mod.load_enabled(self.tmp / "mcp.json"), {"fake": True})

    def test_skipped_without_credential(self):
        self._run(env={})
        entry = self._entry()
        self.assertEqual(entry["status"], "skipped")
        self.assertIsNone(entry["last_ok_at"])
        self.assertEqual(self.sink.alerts, [])

    def test_atomic_write_leaves_no_temp_and_survives_failure(self):
        self._run()
        before = self.state.read_text()
        real_replace = os.replace

        def boom(*a, **k):
            raise OSError("disk full")

        os.replace = boom
        try:
            with self.assertRaises(OSError):
                probe_mod.save_state(self.state, {"version": 1, "targets": {"x": {}}})
        finally:
            os.replace = real_replace
        self.assertEqual(self.state.read_text(), before)
        self.assertEqual([p.name for p in self.state.parent.iterdir()], [self.state.name])

    def test_corrupt_state_recovers(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text("{not json")
        _, _, warning = self._run()
        self.assertIn("starting fresh", warning)
        self.assertEqual(self._entry()["status"], "ok")
        self.assertEqual((self.state.parent / (self.state.name + ".corrupt")).read_text(), "{not json")

    def test_redaction_of_credentials_in_state_and_alerts(self):
        def leaky(target, env, timeout):
            return harness.Result(target.name, harness.AUTH, f"rejected key {SECRET} here")

        self._config("ok")
        probe_mod.run_probe(self.tmp / "mcp.json", self.tmp / "settings.json", self.state,
                            self.env, self.sink, now_fn=self.clock, probe=leaky)
        self.assertNotIn(SECRET, self.state.read_text())
        self.assertNotIn(SECRET, json.dumps(self.sink.alerts))
        self.assertIn("[REDACTED]", self._entry()["last_error_detail"])
        # real harness path: fake server echoes the presented key on auth failure
        self._run(mode="auth_reject")
        self.assertNotIn(SECRET, self.state.read_text())

    def test_status_table_and_json_and_exit_codes(self):
        self._config("ok")
        code, _, err = self._cli()
        self.assertEqual(code, 0, err)
        code, out, _ = self._cli("--status")
        self.assertEqual(code, 0)
        self.assertIn("fake", out)
        self.assertIn("ok", out)
        self.clock.advance(minutes=15)
        code, _, _ = self._cli(mode="missing_tool")
        self.assertEqual(code, 1)
        code, out, _ = self._cli("--status")
        self.assertEqual(code, 1)
        self.assertIn("DISCOVERY", out)
        code, out, _ = self._cli("--json")
        self.assertEqual(code, 1)
        row = json.loads(out)["targets"][0]
        self.assertEqual(row["status"], "failing")
        self.assertEqual(row["last_ok_at"], "2026-10-11T12:00:00Z")
        self.assertEqual(row["last_error_category"], "DISCOVERY")
        self.assertEqual(row["last_error_at"], "2026-10-11T12:15:00Z")
        self.assertNotIn(SECRET, out)

    def test_status_does_not_probe_and_empty_state_is_zero(self):
        self._config("crash")
        code, out, _ = self._cli("--status")
        self.assertEqual(code, 0)
        self.assertFalse(self.state.exists())
        code, _, _ = self._cli("--status", "--require-all")
        self.assertEqual(code, 1)

    def test_state_inside_repo_refused(self):
        self._config("ok")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = probe_mod.main(
                ["--config", str(self.tmp / "mcp.json"), "--state", str(REPO_ROOT / "state.json"), "--status"],
                env={})
        self.assertEqual(code, 2)

    def test_default_state_path_is_outside_repo(self):
        for env in ({}, {"XDG_STATE_HOME": "/tmp/xdg"}):
            self.assertFalse(probe_mod._inside_repo(probe_mod.default_state_path(env)))
        self.assertEqual(probe_mod.default_state_path({"MCP_HEALTH_STATE": "/x/y.json"}), Path("/x/y.json"))


if __name__ == "__main__":
    unittest.main()
