"""Offline validation of the scoped Mission Control checkout's early exits."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BASH = shutil.which("bash")
ROOT = Path(__file__).resolve().parents[1]
GUARDED_SCRIPT = """
curl() { printf 'UNEXPECTED_NETWORK_COMMAND: curl\\n' >&2; exit 99; }
python3() { printf 'UNEXPECTED_NETWORK_COMMAND: hydration\\n' >&2; exit 99; }
aws() { printf 'UNEXPECTED_NETWORK_COMMAND: aws\\n' >&2; exit 99; }
source "$@"
"""

CASES = {
    "wrong-principal": (
        {"MC_RUNTIME": "claude-code", "MC_MCP_PRINCIPAL_ID": "sp_mcp_codex"},
        ["TASK-1"],
        1,
        "claude-code requires sp_mcp_claude_code",
    ),
    "missing-key": (
        {"MC_RUNTIME": "claude-code"},
        ["TASK-1"],
        1,
        "MISSING: set MC_MCP_API_KEY in the Claude environment",
    ),
    "invalid-runtime": (
        {"MC_RUNTIME": "bogus"},
        ["TASK-1"],
        1,
        "must be local, cursor-cloud or claude-code",
    ),
    "bad-operator": ({"MC_OPERATOR_EMAIL": "x@y.z"}, ["TASK-1"], 1, "identity must be"),
    "usage": ({}, [], 2, "usage:"),
}


@unittest.skipIf(BASH is None, "bash is not on PATH")
class CheckoutRejectsBeforeNetworkTests(unittest.TestCase):
    def test_checkout_rejects_before_network(self):
        for name, (overrides, args, exit_code, message) in CASES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as home:
                env = {
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": Path(home).as_posix(),
                }
                if "SYSTEMROOT" in os.environ:
                    env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
                env.update(overrides)
                result = subprocess.run(
                    [
                        BASH,
                        "--noprofile",
                        "--norc",
                        "-c",
                        GUARDED_SCRIPT,
                        "bash",
                        "scripts/mc-checkout-local-inference.sh",
                        *args,
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn(
                    "UNEXPECTED_NETWORK_COMMAND", result.stdout + result.stderr
                )


if __name__ == "__main__":
    unittest.main()
