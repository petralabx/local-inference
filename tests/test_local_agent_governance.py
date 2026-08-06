from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_SCRIPT = REPO_ROOT / "scripts" / "mc-checkout-local-inference.sh"
PREFLIGHT_SCRIPT = REPO_ROOT / "scripts" / "local-agent-preflight.sh"
PUSH_SCRIPT = REPO_ROOT / "scripts" / "push-agent-branch.sh"
WINDOWS_GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(WINDOWS_GIT_BASH) if os.name == "nt" and WINDOWS_GIT_BASH.exists() else "bash"


def _shell_path(path: Path) -> str:
    resolved = path.resolve().as_posix()
    if os.name == "nt":
        drive, remainder = resolved.split(":/", 1)
        return f"/{drive.lower()}/{remainder}"
    return resolved


def _write_executable(path: Path, body: str) -> None:
    path.write_text(
        textwrap.dedent(body).lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(0o755)


class McCheckoutScriptTests(unittest.TestCase):
    def _run(self, curl_body: str, *args: str, env_updates: dict[str, str] | None = None):
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir)
            _write_executable(bin_dir / "curl", curl_body)
            env = os.environ.copy()
            env.update(
                {
                    "TEST_BIN": _shell_path(bin_dir),
                    "MC_MCP_API_KEY": "secret-never-print",
                    "MC_MCP_PRINCIPAL_ID": "sp_mcp_hermes",
                    "MC_OPERATOR_EMAIL": "cos@petrasoap.com",
                    "MC_REPO": "petralabx/local-inference",
                    "MC_RUNTIME": "local",
                }
            )
            if env_updates:
                env.update(env_updates)
            return subprocess.run(
                [
                    BASH,
                    "-c",
                    'PATH="$TEST_BIN:$PATH"; exec bash "$@"',
                    "test-shell",
                    _shell_path(CHECKOUT_SCRIPT),
                    *args,
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_self_check_is_non_mutating_and_redacts_credential(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf 'curl-argv:%s\n' "$*" >&2
            printf '%s\n' '{"data":{"ok":true},"meta":{"actor":{"repo":"petralabx/local-inference","operatorEmail":"cos@petrasoap.com","runtime":"local","servicePrincipalId":"sp_mcp_hermes"}}}'
            """,
            "--self-check",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"actorRepo": "petralabx/local-inference"', result.stdout)
        self.assertNotIn("secret-never-print", result.stdout + result.stderr)
        self.assertNotIn("/api/cursor/checkout", result.stdout + result.stderr)

    def test_self_check_rejects_wrong_repository_scope(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf '%s\n' '{"data":{"ok":true},"meta":{"actor":{"repo":"other/repo","operatorEmail":"cos@petrasoap.com","runtime":"local","servicePrincipalId":"sp_mcp_hermes"}}}'
            """,
            "--self-check",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("identity mismatch", result.stderr)

    def test_local_runtime_does_not_attempt_aws_hydration(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf 'curl must not run\n' >&2
            exit 99
            """,
            "--self-check",
            env_updates={"PLX_MC_MCP_API_KEY": "", "MC_MCP_API_KEY": ""},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("set MC_MCP_API_KEY in the local agent environment", result.stderr)
        self.assertNotIn("curl must not run", result.stderr)

    def test_checkout_validates_full_identity_and_returns_stamp(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            if [[ "$*" == *"/api/cursor/checkout"* ]]; then
              printf '%s\n' '{"data":{"taskId":"TASK-910","checkoutId":"dsp_test123","prBodyLine":"MC-Checkout: dsp_test123"},"meta":{"actor":{"repo":"petralabx/local-inference","operatorEmail":"cos@petrasoap.com","runtime":"local","servicePrincipalId":"sp_mcp_hermes"}}}'
            else
              printf '%s\n' '{"data":{"ok":true},"meta":{"actor":{"repo":"petralabx/local-inference","operatorEmail":"cos@petrasoap.com","runtime":"local","servicePrincipalId":"sp_mcp_hermes"}}}'
            fi
            """,
            "TASK-910",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MC-Checkout: dsp_test123", result.stdout)
        self.assertNotIn("secret-never-print", result.stdout + result.stderr)

    def test_self_check_rejects_runtime_mismatch(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf '%s\n' '{"data":{"ok":true},"meta":{"actor":{"repo":"petralabx/local-inference","operatorEmail":"cos@petrasoap.com","runtime":"cursor-cloud","servicePrincipalId":"sp_mcp_cursor"}}}'
            """,
            "--self-check",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn('"runtime": "cursor-cloud"', result.stderr)

    def test_noncanonical_mc_base_url_is_rejected_before_curl(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf 'curl must not run\n' >&2
            exit 99
            """,
            "--self-check",
            env_updates={"MC_BASE_URL": "https://example.invalid"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("MC_BASE_URL must be https://mc.plxcustomer.io", result.stderr)
        self.assertNotIn("curl must not run", result.stderr)

    def test_caller_cannot_override_repository_identity(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf 'curl must not run\n' >&2
            exit 99
            """,
            "--self-check",
            env_updates={"MC_REPO": "other/repo"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("identity must be repo=petralabx/local-inference", result.stderr)
        self.assertNotIn("curl must not run", result.stderr)

    def test_local_runtime_requires_explicit_dedicated_principal(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf '%s\n' '{"data":{"ok":true},"meta":{"actor":{"repo":"petralabx/local-inference","operatorEmail":"cos@petrasoap.com","runtime":"local","servicePrincipalId":"sp_mcp_cursor"}}}'
            """,
            "--self-check",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn('"servicePrincipalId": "sp_mcp_cursor"', result.stderr)

    def test_local_runtime_rejects_unreviewed_principal_before_curl(self):
        result = self._run(
            """
            #!/usr/bin/env bash
            printf 'curl must not run\n' >&2
            exit 99
            """,
            "--self-check",
            env_updates={"MC_MCP_PRINCIPAL_ID": "sp_mcp_unreviewed"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("unsupported MC_MCP_PRINCIPAL_ID", result.stderr)
        self.assertNotIn("curl must not run", result.stderr)


class LocalAgentPreflightTests(unittest.TestCase):
    def _run(
        self,
        *args: str,
        origin: str = "https://github.com/petralabx/local-inference.git",
        push_url: str = "https://github.com/petralabx/local-inference.git",
        branch: str = "cursor/local-parity",
        include_credentials: bool = True,
        python_bin: str | None = None,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            _write_executable(
                bin_dir / "git",
                """
                #!/usr/bin/env bash
                case "$1 $2" in
                  "rev-parse --show-toplevel") printf '%s\n' "$FAKE_REPO_ROOT" ;;
                  "remote get-url")
                    if [[ "${3:-}" == "--push" ]]; then
                      printf '%s\n' "$FAKE_PUSH_URL"
                    else
                      printf '%s\n' "$FAKE_ORIGIN"
                    fi
                    ;;
                  "branch --show-current") printf '%s\n' "$FAKE_BRANCH" ;;
                  "push --dry-run") exit 0 ;;
                  *) exit 1 ;;
                esac
                """,
            )
            _write_executable(
                bin_dir / "gh",
                """
                #!/usr/bin/env bash
                if [[ "$1" == "api" ]]; then
                  printf 'true\n'
                  exit 0
                fi
                exit 1
                """,
            )
            for tool in ("node", "jq", "curl"):
                _write_executable(bin_dir / tool, "#!/usr/bin/env bash\nexit 0\n")
            mc_check = root / "mc-check"
            _write_executable(mc_check, "#!/usr/bin/env bash\nexit 0\n")

            env = os.environ.copy()
            env.update(
                {
                    "TEST_BIN": _shell_path(bin_dir),
                    "FAKE_REPO_ROOT": str(REPO_ROOT),
                    "FAKE_ORIGIN": origin,
                    "FAKE_PUSH_URL": push_url,
                    "FAKE_BRANCH": branch,
                    "MC_CHECKOUT_SCRIPT": _shell_path(mc_check),
                }
            )
            if python_bin is not None:
                env["PYTHON_BIN"] = python_bin
            if include_credentials:
                env.update(
                    {
                        "MC_MCP_API_KEY": "secret-never-print",
                        "MC_MCP_PRINCIPAL_ID": "sp_mcp_hermes",
                        "MC_OPERATOR_EMAIL": "cos@petrasoap.com",
                        "MC_REPO": "petralabx/local-inference",
                        "MC_RUNTIME": "local",
                    }
                )
            else:
                for key in (
                    "PLX_MC_MCP_API_KEY",
                    "MC_MCP_API_KEY",
                    "MC_MCP_PRINCIPAL_ID",
                    "MC_OPERATOR_EMAIL",
                    "MC_REPO",
                    "MC_RUNTIME",
                ):
                    env.pop(key, None)

            return subprocess.run(
                [
                    BASH,
                    "-c",
                    'PATH="$TEST_BIN:$PATH"; exec bash "$@"',
                    "test-shell",
                    _shell_path(PREFLIGHT_SCRIPT),
                    *args,
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_online_preflight_passes_without_printing_secrets(self):
        result = self._run("--online")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("READY: local agent can begin governed work", result.stdout)
        self.assertNotIn("secret-never-print", result.stdout + result.stderr)

    def test_offline_preflight_allows_unprovisioned_credentials(self):
        result = self._run("--offline", branch="main", include_credentials=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("offline structure checks passed", result.stdout)
        self.assertIn("MC_MCP_API_KEY is not set", result.stdout)

    def test_wrong_origin_fails(self):
        result = self._run(
            "--online", origin="https://github.com/taylorvalton/local-inference-dev.git"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("origin fetch URL must target petralabx/local-inference", result.stderr)

    def test_deceptive_hostname_fails(self):
        result = self._run(
            "--online",
            origin="https://evilgithub.com/petralabx/local-inference.git",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("origin fetch URL must target", result.stderr)

    def test_mismatched_push_url_fails(self):
        result = self._run(
            "--online",
            push_url="https://github.com/attacker/local-inference.git",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("origin push URL must target", result.stderr)

    def test_unavailable_configured_python_fails(self):
        result = self._run("--offline", python_bin="/missing/python")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Python 3 is required", result.stderr)


class PushAgentBranchTests(unittest.TestCase):
    def _run(
        self,
        branch: str,
        *,
        origin: str = "https://github.com/petralabx/local-inference.git",
        push_url: str = "https://github.com/petralabx/local-inference.git",
        dirty: bool = False,
        python_exit: int = 0,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            command_log = root / "git.log"
            _write_executable(
                bin_dir / "git",
                """
                #!/usr/bin/env bash
                printf '%s\n' "$*" >> "$FAKE_GIT_LOG"
                case "$1 $2" in
                  "rev-parse --show-toplevel") printf '%s\n' "$FAKE_REPO_ROOT" ;;
                  "remote get-url")
                    if [[ "${3:-}" == "--push" ]]; then
                      printf '%s\n' "$FAKE_PUSH_URL"
                    else
                      printf '%s\n' "$FAKE_ORIGIN"
                    fi
                    ;;
                  "branch --show-current") printf '%s\n' "$FAKE_BRANCH" ;;
                  "status --porcelain")
                    [[ "$FAKE_DIRTY" == "1" ]] && printf ' M changed-file\n'
                    exit 0
                    ;;
                  "cat-file -e") exit 0 ;;
                  "diff --quiet") exit 0 ;;
                  "push -u") exit 0 ;;
                  *) exit 1 ;;
                esac
                """,
            )
            python_bin = bin_dir / "python"
            _write_executable(
                python_bin, f"#!/usr/bin/env bash\nexit {python_exit}\n"
            )
            env = os.environ.copy()
            env.update(
                {
                    "TEST_BIN": _shell_path(bin_dir),
                    "PYTHON_BIN": _shell_path(python_bin),
                    "FAKE_GIT_LOG": _shell_path(command_log),
                    "FAKE_REPO_ROOT": str(root),
                    "FAKE_ORIGIN": origin,
                    "FAKE_PUSH_URL": push_url,
                    "FAKE_BRANCH": branch,
                    "FAKE_DIRTY": "1" if dirty else "0",
                }
            )
            result = subprocess.run(
                [
                    BASH,
                    "-c",
                    'PATH="$TEST_BIN:$PATH"; exec bash "$@"',
                    "test-shell",
                    _shell_path(PUSH_SCRIPT),
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            return result, command_log.read_text(encoding="utf-8")

    def test_verified_push_accepts_only_cursor_branch(self):
        result, command_log = self._run("cursor/local-parity")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("push -u origin cursor/local-parity", command_log)

    def test_verified_push_rejects_main(self):
        result, command_log = self._run("main")

        self.assertEqual(result.returncode, 1)
        self.assertIn("branch must match cursor/*", result.stderr)
        self.assertNotIn("push -u", command_log)

    def test_verified_push_rejects_alternate_push_url(self):
        result, command_log = self._run(
            "cursor/local-parity",
            push_url="ssh://git@evilgithub.com/petralabx/local-inference.git",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one canonical push URL", result.stderr)
        self.assertNotIn("push -u", command_log)

    def test_verified_push_rejects_dirty_tree(self):
        result, command_log = self._run("cursor/local-parity", dirty=True)

        self.assertEqual(result.returncode, 1)
        self.assertIn("commit or remove working-tree changes", result.stderr)
        self.assertNotIn("push -u", command_log)

    def test_verified_push_stops_when_validation_fails(self):
        result, command_log = self._run("cursor/local-parity", python_exit=1)

        self.assertEqual(result.returncode, 1)
        self.assertNotIn("push -u", command_log)


if __name__ == "__main__":
    unittest.main()
