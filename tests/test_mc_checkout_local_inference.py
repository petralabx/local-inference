"""Offline validation of the scoped Mission Control checkout's early exits."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


BASH = shutil.which("bash")
if BASH is None:
    pytest.skip("bash is not on PATH", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[1]
GUARDED_SCRIPT = """
curl() { printf 'UNEXPECTED_NETWORK_COMMAND: curl\\n' >&2; exit 99; }
python3() { printf 'UNEXPECTED_NETWORK_COMMAND: hydration\\n' >&2; exit 99; }
aws() { printf 'UNEXPECTED_NETWORK_COMMAND: aws\\n' >&2; exit 99; }
source "$@"
"""


@pytest.mark.parametrize(
    "overrides,args,exit_code,message",
    [
        (
            {"MC_RUNTIME": "claude-code", "MC_MCP_PRINCIPAL_ID": "sp_mcp_codex"},
            ["TASK-1"],
            1,
            "claude-code requires sp_mcp_claude_code",
        ),
        (
            {"MC_RUNTIME": "claude-code"},
            ["TASK-1"],
            1,
            "MISSING: set MC_MCP_API_KEY in the Claude environment",
        ),
        (
            {"MC_RUNTIME": "bogus"},
            ["TASK-1"],
            1,
            "must be local, cursor-cloud or claude-code",
        ),
        (
            {"MC_OPERATOR_EMAIL": "x@y.z"},
            ["TASK-1"],
            1,
            "identity must be",
        ),
        ({}, [], 2, "usage:"),
    ],
    ids=["wrong-principal", "missing-key", "invalid-runtime", "bad-operator", "usage"],
)
def test_checkout_rejects_before_network(tmp_path, overrides, args, exit_code, message):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp_path.as_posix()}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    env.update(overrides)
    result = subprocess.run(
        [BASH, "--noprofile", "--norc", "-c", GUARDED_SCRIPT,
         "bash", "scripts/mc-checkout-local-inference.sh", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == exit_code, result.stderr
    assert message in result.stderr
    assert "UNEXPECTED_NETWORK_COMMAND" not in result.stdout + result.stderr
