"""Offline tests for scripts/smoke_mcp_targets.py against a fake stdio MCP server."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_SERVER = REPO_ROOT / "tests" / "fixtures" / "fake_mcp_server.py"
SECRET = "sk-test-smoke-secret-12345"


def _load_harness():
    path = REPO_ROOT / "scripts" / "smoke_mcp_targets.py"
    spec = importlib.util.spec_from_file_location("smoke_mcp_targets", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_mcp_targets"] = module
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


class SmokeHarnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _run(self, mode="ok", env=None, extra_args=(), key=SECRET):
        config = {
            "mcpServers": {
                "fake": {
                    "command": sys.executable,
                    "args": [str(FAKE_SERVER)],
                    "env": {
                        "FAKE_MCP_MODE": mode,
                        "FAKE_MCP_KEY": key,
                        "FAKE_MCP_PRESENTED": "${FAKE_SMOKE_KEY}",
                    },
                }
            }
        }
        settings = {
            "permissions": {
                "allow": ["mcp__fake__mc_self_check", "mcp__fake__mc_get_context"]
            }
        }
        (self.tmp / "mcp.json").write_text(json.dumps(config))
        (self.tmp / "settings.json").write_text(json.dumps(settings))
        argv = [
            "--config", str(self.tmp / "mcp.json"),
            "--settings", str(self.tmp / "settings.json"),
            "--timeout", "5",
            *extra_args,
        ]
        out, err = io.StringIO(), io.StringIO()
        env = {"FAKE_SMOKE_KEY": SECRET} if env is None else env
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = harness.main(argv, env=env)
        return code, out.getvalue(), err.getvalue()

    def test_happy_path_passes(self):
        code, out, _ = self._run()
        self.assertEqual(code, 0, out)
        self.assertIn("fake: PASS", out)
        self.assertIn("1 passed, 0 failed, 0 skipped", out)

    def test_startup_crash_is_startup_failure(self):
        code, out, _ = self._run(mode="crash")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [STARTUP]", out)
        self.assertIn("fake server boot failure", out)

    def test_missing_executable_is_startup_failure(self):
        config = {"mcpServers": {"fake": {"command": "/nonexistent/mcp-server"}}}
        (self.tmp / "mcp.json").write_text(json.dumps(config))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = harness.main(
                ["--config", str(self.tmp / "mcp.json"), "--settings", str(self.tmp / "none.json")],
                env={},
            )
        self.assertEqual(code, 1)
        self.assertIn("[STARTUP]", out.getvalue())

    def test_hang_times_out_as_startup_failure(self):
        code, out, _ = self._run(mode="hang", extra_args=("--timeout", "2"))
        self.assertEqual(code, 1)
        self.assertIn("[STARTUP]", out)
        self.assertIn("timed out", out)

    def test_missing_tool_is_discovery_failure(self):
        code, out, _ = self._run(mode="missing_tool")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [DISCOVERY]", out)
        self.assertIn("mc_get_context", out)

    def test_rejected_credential_is_auth_failure(self):
        code, out, _ = self._run(mode="auth_reject")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [AUTH]", out)

    def test_wrong_credential_is_auth_failure(self):
        code, out, _ = self._run(key="a-different-key")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [AUTH]", out)

    def test_malformed_protocol_is_protocol_failure(self):
        code, out, _ = self._run(mode="malformed")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [PROTOCOL]", out)

    def test_credential_is_redacted_from_output(self):
        for mode in ("ok", "auth_reject", "malformed", "missing_tool", "crash"):
            with self.subTest(mode=mode):
                code, out, err = self._run(mode=mode)
                self.assertNotIn(SECRET, out + err)
        _, out, _ = self._run(mode="auth_reject")
        self.assertIn(harness.REDACTED, out)

    def test_absent_credential_is_skipped_not_passed(self):
        code, out, _ = self._run(env={})
        self.assertEqual(code, 0)
        self.assertIn("fake: SKIPPED (no credential)", out)
        self.assertIn("0 passed, 0 failed, 1 skipped", out)

    def test_empty_credential_is_skipped(self):
        code, out, _ = self._run(env={"FAKE_SMOKE_KEY": ""})
        self.assertIn("SKIPPED (no credential)", out)

    def test_require_all_turns_skip_into_failure(self):
        code, out, err = self._run(env={}, extra_args=("--require-all",))
        self.assertEqual(code, 1)
        self.assertIn("SKIPPED (no credential)", out)
        self.assertIn("--require-all", err)

    def test_unknown_target_is_config_error(self):
        code, _, err = self._run(extra_args=("--target", "nope"))
        self.assertEqual(code, 2)
        self.assertIn("unknown target", err)


class _Rejecting(BaseHTTPRequestHandler):
    seen_auth: list[str] = []

    def do_POST(self):
        type(self).seen_auth.append(self.headers.get("Authorization", ""))
        self.send_response(401)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class HttpTransportTests(unittest.TestCase):
    def _run(self, url):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = Path(tmp.name) / "mcp.json"
        config.write_text(json.dumps({"mcpServers": {"web": {
            "type": "http", "url": url,
            "headers": {"Authorization": "Bearer ${WEB_KEY}"},
        }}}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = harness.main(
                ["--config", str(config), "--settings", str(Path(tmp.name) / "s.json"), "--timeout", "10"],
                env={"WEB_KEY": SECRET},
            )
        return code, out.getvalue()

    def test_http_401_is_auth_failure_and_sends_bearer(self):
        _Rejecting.seen_auth = []
        server = HTTPServer(("127.0.0.1", 0), _Rejecting)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        code, out = self._run(f"http://127.0.0.1:{server.server_port}/mcp")
        self.assertEqual(code, 1)
        self.assertIn("FAIL [AUTH]", out)
        self.assertNotIn(SECRET, out)
        self.assertEqual(_Rejecting.seen_auth[0], f"Bearer {SECRET}")

    def test_http_unreachable_is_startup_failure(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        code, out = self._run(f"http://127.0.0.1:{port}/mcp")
        self.assertEqual(code, 1)
        self.assertIn("[STARTUP]", out)
        self.assertNotIn(SECRET, out)


class RepoConfigTests(unittest.TestCase):
    def test_repo_mcp_json_targets_discovered(self):
        targets = harness.load_targets(harness.DEFAULT_CONFIG, harness.DEFAULT_SETTINGS)
        by_name = {t.name: t for t in targets}
        hub = by_name["PLX-MC-Hub"]
        self.assertEqual(hub.transport, "http")
        self.assertEqual(hub.required_env, ["MC_MCP_API_KEY"])
        self.assertIn("mc_self_check", hub.expected_tools)
        self.assertEqual(hub.self_check_tool, "mc_self_check")

    def test_expand_uses_env_and_defaults(self):
        self.assertEqual(harness.expand("${A}-${B:-dflt}", {"A": "x"}), "x-dflt")

    def test_repo_run_without_credentials_skips_everything(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = harness.main([], env={})
        self.assertEqual(code, 0)
        self.assertIn("PLX-MC-Hub: SKIPPED (no credential)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
