"""Offline source resolution tests; all synthetic checkouts live in temp dirs."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("mcp_roots", SCRIPTS / "mcp_roots.py")
roots = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = roots
spec.loader.exec_module(roots)


class RootTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.own = self.checkout("own")
        self.other = self.checkout("other")

    def checkout(self, name):
        root = self.tmp / name
        (root / "config").mkdir(parents=True)
        (root / "config" / "execution-primitives.local.yaml").write_text(
            "repo: petralabx/local-inference\n"
        )
        (root / ".mcp.json").write_text('{"mcpServers": {}}')
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text("{}")
        return root

    def resolve(self, **kwargs):
        return roots.resolve_sources(script_root=self.own, cwd=self.tmp, **kwargs)

    def test_root_flag_beats_all_source_environment_overrides(self):
        result = self.resolve(
            root=self.own,
            env={
                "LOCAL_INFERENCE_ROOT": str(self.tmp / "invalid"),
                "MCP_CONFIG_PATH": str(self.tmp / "missing"),
                "MCP_SETTINGS_PATH": str(self.tmp / "missing"),
            },
        )
        self.assertEqual(result.root, self.own)
        self.assertEqual(result.config, self.own / ".mcp.json")
        self.assertEqual(result.settings, self.own / ".claude" / "settings.json")

    def test_path_flags_beat_environment(self):
        result = self.resolve(
            config=self.other / ".mcp.json",
            settings=self.other / ".claude" / "settings.json",
            env={"MCP_CONFIG_PATH": "/missing", "MCP_SETTINGS_PATH": "/missing"},
        )
        self.assertEqual(result.config, self.other / ".mcp.json")
        self.assertEqual(result.settings, self.other / ".claude" / "settings.json")

    def test_environment_beats_discovery(self):
        result = self.resolve(env={"LOCAL_INFERENCE_ROOT": str(self.other)})
        self.assertEqual(result.root, self.other)
        result = self.resolve(
            env={
                "MCP_CONFIG_PATH": str(self.other / ".mcp.json"),
                "MCP_SETTINGS_PATH": str(self.other / ".claude" / "settings.json"),
            }
        )
        self.assertEqual(result.config, self.other / ".mcp.json")
        self.assertEqual(result.settings, self.other / ".claude" / "settings.json")

    def test_invalid_overrides_fail_without_fallback(self):
        for name in ("LOCAL_INFERENCE_ROOT", "MCP_CONFIG_PATH", "MCP_SETTINGS_PATH"):
            with self.subTest(name=name), self.assertRaises(roots.RootError) as error:
                self.resolve(env={name: str(self.tmp / "missing")})
            self.assertIn(name, str(error.exception))
            self.assertIn(str(self.tmp / "missing"), str(error.exception))
            self.assertIn("Tried:", str(error.exception))

    def test_wrong_repository_and_missing_mcp_config_rejected(self):
        marker = self.other / "config" / "execution-primitives.local.yaml"
        marker.write_text("repo: example/other\n")
        with self.assertRaises(roots.RootError):
            self.resolve(root=self.other, env={})
        marker.write_text("repo: petralabx/local-inference\n")
        (self.other / ".mcp.json").unlink()
        with self.assertRaises(roots.RootError):
            self.resolve(root=self.other, env={})

    def test_own_checkout_discovery_wins(self):
        with patch.object(roots.subprocess, "run") as git:
            result = self.resolve(env={})
        self.assertEqual(result.root, self.own)
        git.assert_not_called()

    def test_discovery_from_nested_cwd(self):
        subprocess.run(["git", "init", "-q", str(self.other)], check=True)
        nested = self.other / "nested" / "deep"
        nested.mkdir(parents=True)
        result = roots.resolve_sources(
            env={}, script_root=self.tmp / "absent", cwd=nested
        )
        self.assertEqual(result.root, self.other)

    def test_standalone_files_and_optional_cli_settings(self):
        result = roots.resolve_sources(
            config=self.other / ".mcp.json",
            settings=self.tmp / "optional.json",
            env={},
            script_root=self.tmp / "absent",
            cwd=self.tmp,
        )
        self.assertIsNone(result.root)
        self.assertEqual(result.settings, self.tmp / "optional.json")

    def test_both_entrypoints_no_checkout_exit_with_tried_paths(self):
        detached = self.tmp / "detached"
        detached.mkdir()
        for name in ("mcp_roots.py", "smoke_mcp_targets.py", "mcp_health_probe.py"):
            shutil.copyfile(SCRIPTS / name, detached / name)
        for name in ("smoke_mcp_targets.py", "mcp_health_probe.py"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(detached / name)],
                    env={"PATH": os.defpath},
                    cwd=self.tmp,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                for expected in (
                    "LOCAL_INFERENCE_ROOT",
                    "MCP_CONFIG_PATH",
                    "MCP_SETTINGS_PATH",
                    "Tried:",
                    str(self.tmp),
                    str(detached.parent),
                    "CWD git toplevel",
                ):
                    self.assertIn(expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_both_entrypoints_invalid_override_is_config_error(self):
        for name in ("smoke_mcp_targets.py", "mcp_health_probe.py"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / name)],
                    env={"PATH": os.defpath, "LOCAL_INFERENCE_ROOT": str(self.tmp)},
                    cwd=self.tmp,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("invalid checkout override", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_probe_refuses_state_in_selected_checkout(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "mcp_health_probe.py"),
                "--root",
                str(self.other),
                "--status",
                "--state",
                str(self.other / "state.json"),
            ],
            env={"PATH": os.defpath},
            cwd=self.tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("inside the repo tree", result.stderr)
        self.assertFalse((self.other / "state.json").exists())

    def test_probe_root_override_status_without_probing(self):
        (self.other / ".mcp.json").write_text(
            '{"mcpServers": {"fake": {"command": "unused"}}}'
        )
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "mcp_health_probe.py"),
                "--root",
                str(self.other),
                "--status",
                "--state",
                str(self.tmp / "state.json"),
            ],
            env={"PATH": os.defpath},
            cwd=self.tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TARGET", result.stdout)
        self.assertFalse((self.tmp / "state.json").exists())


class DeploymentTests(unittest.TestCase):
    setUp = RootTests.setUp
    checkout = RootTests.checkout

    def test_systemd_command_uses_environment_root_with_spaces(self):
        root = self.checkout("deployment with spaces")
        interpreter = root / ".venv" / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text('#!/bin/sh\npwd\nprintf "%s\\n" "$@"\n')
        interpreter.chmod(0o755)
        unit = (
            SCRIPTS.parent / "deploy" / "mcp-health" / "mcp-health-probe.service"
        ).read_text()
        command = next(
            line.removeprefix("ExecStart=/bin/sh -c ")
            for line in unit.splitlines()
            if line.startswith("ExecStart=")
        )
        # systemd turns $$ into $ before invoking the shell.
        command = command[1:-1].replace("$$", "$")
        result = subprocess.run(
            ["/bin/sh", "-c", command],
            cwd=self.tmp,
            env={"PATH": os.defpath, "LOCAL_INFERENCE_ROOT": str(root)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(), [str(root), "scripts/mcp_health_probe.py"]
        )

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell unavailable")
    def test_windows_registrar_flag_and_environment_root(self):
        registrar = SCRIPTS / "register_mcp_health_probe.ps1"
        # Mock task construction only; never register or install a task.
        driver = self.tmp / "preview.ps1"
        driver.write_text(
            "param([string]$Registrar, [string]$Root)\n"
            "function New-ScheduledTaskAction { param($Execute, $Argument, $WorkingDirectory) "
            'Write-Output "ACTION=$Execute|$Argument|$WorkingDirectory" }\n'
            "function New-ScheduledTaskTrigger { param([switch]$Once, $At, $RepetitionInterval) }\n"
            "function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable, $MultipleInstances, $ExecutionTimeLimit) }\n"
            "if ($Root) { & $Registrar -RepoRoot $Root } else { & $Registrar }\n"
        )
        for flag in (False, True):
            with self.subTest(flag=flag):
                selected = self.other if flag else self.own
                args = [
                    "pwsh",
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(driver),
                    str(registrar),
                ]
                if flag:
                    args.append(str(selected))
                result = subprocess.run(
                    args,
                    cwd=self.tmp,
                    env={"PATH": os.defpath, "LOCAL_INFERENCE_ROOT": str(self.own)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(str(selected), result.stdout)
                self.assertIn('--root "' + str(selected) + '"', result.stdout)
                self.assertIn(".venv", result.stdout)


if __name__ == "__main__":
    unittest.main()
