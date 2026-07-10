from __future__ import annotations

import importlib.util
import io
import json
import os
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch


def _load_worker_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "ask_local_worker.py"
    spec = importlib.util.spec_from_file_location("ask_local_worker", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load ask_local_worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MockChatServer:
    def __init__(self, status_code: int = 200, response_body: dict | None = None):
        self.status_code = status_code
        self.response_body = response_body or {"choices": [{"message": {"content": "ok"}}]}
        self.requests: list[dict] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def __enter__(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = self.rfile.read(length)
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": payload,
                    }
                )
                self.send_response(outer.status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(outer.response_body).encode("utf-8"))

            def log_message(self, _format: str, *_args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return False

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("Server not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"


class AskLocalWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_worker_module()

    def test_request_body_headers_and_no_think_append(self):
        with TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.local"
            env_file.write_text("LOCAL_LITELLM_MASTER_KEY=sk-file-key\n", encoding="utf-8")
            with MockChatServer() as server:
                stdout = io.StringIO()
                stderr = io.StringIO()
                code = self.mod.main(
                    argv=[
                        "--model",
                        "local-primary",
                        "--base-url",
                        server.base_url,
                        "--env-file",
                        str(env_file),
                        "--prompt",
                        "Hello from test",
                    ],
                    environ={},
                    stdout=stdout,
                    stderr=stderr,
                )

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(stdout.getvalue().strip(), "ok")
        self.assertEqual(len(server.requests), 1)
        req = server.requests[0]
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["headers"]["authorization"], "Bearer sk-file-key")
        body = json.loads(req["body"].decode("utf-8"))
        self.assertEqual(body["model"], "local-primary")
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn("/no_think", body["messages"][0]["content"])

    def test_environment_key_takes_precedence_over_env_file(self):
        with TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.local"
            env_file.write_text(
                "LOCAL_LITELLM_MASTER_KEY=sk-from-file\n", encoding="utf-8"
            )
            with MockChatServer() as server:
                stdout = io.StringIO()
                stderr = io.StringIO()
                code = self.mod.main(
                    argv=[
                        "--base-url",
                        server.base_url,
                        "--env-file",
                        str(env_file),
                        "use env precedence",
                    ],
                    environ={"LOCAL_LITELLM_MASTER_KEY": "sk-from-env"},
                    stdout=stdout,
                    stderr=stderr,
                )

        self.assertEqual(code, 0, stderr.getvalue())
        req = server.requests[0]
        self.assertEqual(req["headers"]["authorization"], "Bearer sk-from-env")

    def test_missing_and_invalid_keys_are_rejected(self):
        with TemporaryDirectory() as tmpdir:
            missing_env_file = Path(tmpdir) / "missing.env"
            with self.assertRaisesRegex(
                self.mod.WorkerClientError, "is not set"
            ):
                self.mod.resolve_master_key({}, "", missing_env_file)
            with self.assertRaisesRegex(
                self.mod.WorkerClientError, "appears invalid"
            ):
                self.mod.resolve_master_key(
                    {"LOCAL_LITELLM_MASTER_KEY": "CHANGE-ME"},
                    "",
                    missing_env_file,
                )

    def test_strip_thinking_blocks(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "<think>plan</think>\n"
                            "Answer body\n"
                            "<redacted_thinking>hidden</redacted_thinking>\n"
                            "Done."
                        )
                    }
                }
            ]
        }
        cleaned = self.mod.extract_clean_content(response, "local-fast")
        self.assertEqual(cleaned, "Answer body\nDone.")

    def test_error_and_empty_response_handling(self):
        with MockChatServer(
            status_code=500, response_body={"error": {"message": "backend exploded"}}
        ) as server:
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = self.mod.main(
                argv=[
                    "--base-url",
                    server.base_url,
                    "--prompt",
                    "trigger error",
                ],
                environ={"LOCAL_LITELLM_MASTER_KEY": "sk-error"},
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(code, 1)
        self.assertIn("HTTP 500: backend exploded", stderr.getvalue())

        response = {"choices": [{"message": {"content": "<think>only hidden</think>"}}]}
        with self.assertRaisesRegex(self.mod.WorkerClientError, "Empty content"):
            self.mod.extract_clean_content(response, "local-primary")

    def test_http_proxy_argument_builds_proxy_handler_and_rejects_socks(self):
        opener = self.mod.build_opener("http://127.0.0.1:1054")
        proxy_handlers = [
            handler
            for handler in opener.handlers
            if isinstance(handler, urllib.request.ProxyHandler)
        ]
        self.assertTrue(proxy_handlers)
        self.assertEqual(
            proxy_handlers[0].proxies,
            {"http": "http://127.0.0.1:1054", "https": "http://127.0.0.1:1054"},
        )
        with self.assertRaisesRegex(
            self.mod.WorkerClientError, "Use HTTP/HTTPS URL"
        ):
            self.mod.build_opener("socks5h://127.0.0.1:1055")

    def test_empty_proxy_ignores_ambient_proxy_environment(self):
        ambient = {
            "HTTP_PROXY": "http://ambient-proxy.invalid:8080",
            "HTTPS_PROXY": "http://ambient-proxy.invalid:8080",
        }
        with patch.dict(os.environ, ambient), patch.object(
            self.mod.urllib.request, "build_opener"
        ) as build_opener_mock:
            self.mod.build_opener("")
        handler = build_opener_mock.call_args.args[0]
        self.assertIsInstance(handler, urllib.request.ProxyHandler)
        self.assertEqual(handler.proxies, {})

    def test_http_error_never_prints_master_key(self):
        secret = "sk-never-print-this-key"
        response = {"error": {"message": f"request used {secret}"}}
        with MockChatServer(status_code=500, response_body=response) as server:
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = self.mod.main(
                argv=["--base-url", server.base_url, "--prompt", "trigger error"],
                environ={"LOCAL_LITELLM_MASTER_KEY": secret},
                stdout=stdout,
                stderr=stderr,
            )
        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(code, 1)
        self.assertNotIn(secret, output)
        self.assertIn("[REDACTED]", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
