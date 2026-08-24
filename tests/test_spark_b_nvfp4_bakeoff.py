from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROD_CONFIG = REPO_ROOT / "litellm" / "config.yaml"
EXAMPLE_CONFIG = REPO_ROOT / "litellm" / "config.spark-b-nvfp4.example.yaml"
SERVE_SCRIPT = REPO_ROOT / "scripts" / "start_spark_b_vllm_qwen36_nvfp4_mtp.sh"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "spark-b-qwen36-nvfp4-bakeoff.md"
STOCK = "nvidia/Qwen3.6-35B-A3B-NVFP4"
PREFERRED = "THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP"
POST_CUTOVER = "POST_CUTOVER_DO_NOT_LEAVE_LOCAL_PRIMARY_ON_DELL"


def _run_script(env_updates: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_updates)
    return subprocess.run(
        ["bash", str(SERVE_SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class LiveConfigUnchangedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PROD_CONFIG.read_text(encoding="utf-8")

    def test_live_aliases_stay_on_current_ports(self):
        self.assertIn("model_name: local-driver", self.text)
        self.assertIn("api_base: http://100.92.253.61:18090/v1", self.text)
        self.assertIn("model_name: local-coder", self.text)
        self.assertIn("api_base: http://100.111.220.1:18082/v1", self.text)
        self.assertIn("model_name: local-primary", self.text)
        self.assertIn("api_base: http://127.0.0.1:8000/v1", self.text)
        self.assertNotIn("model_name: local-driver-nvfp4", self.text)
        self.assertNotIn(":18091", self.text)
        self.assertNotIn(STOCK, self.text)

    def test_db_unavailable_allow_and_master_key_already_present(self):
        self.assertIn("allow_requests_on_db_unavailable: true", self.text)
        self.assertIn("master_key: os.environ/LITELLM_MASTER_KEY", self.text)


class ExampleOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = EXAMPLE_CONFIG.read_text(encoding="utf-8")

    def test_adds_nvfp4_alias_without_replacing_gguf_driver(self):
        self.assertIn("model_name: local-driver-nvfp4", self.text)
        self.assertIn("api_base: http://100.92.253.61:18091/v1", self.text)
        self.assertIn("model_name: local-driver", self.text)
        self.assertIn("api_base: http://100.92.253.61:18090/v1", self.text)
        self.assertIn("model_name: local-coder", self.text)
        self.assertIn("api_base: http://100.111.220.1:18082/v1", self.text)
        self.assertNotIn(STOCK, self.text)
        self.assertIn(POST_CUTOVER, self.text)
        driver_idx = self.text.index("model_name: local-driver\n")
        nvfp4_idx = self.text.index("model_name: local-driver-nvfp4")
        self.assertLess(driver_idx, nvfp4_idx)

    def test_example_does_not_point_local_primary_at_spark_b(self):
        primary_block = self.text.split("model_name: local-primary", 1)[1].split(
            "model_name: local-fast", 1
        )[0]
        self.assertIn("127.0.0.1:8000", primary_block)
        self.assertNotIn("100.92.253.61", primary_block)
        self.assertNotIn("18091", primary_block)


class ServeScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SERVE_SCRIPT.read_text(encoding="utf-8")

    def test_script_is_spark_b_side_port_with_required_flags(self):
        self.assertIn("18091", self.text)
        self.assertIn("--kv-cache-dtype", self.text)
        self.assertIn("fp8", self.text)
        self.assertIn("num_speculative_tokens", self.text)
        self.assertIn("--enable-prefix-caching", self.text)
        self.assertIn(PREFERRED, self.text)
        self.assertIn("spark-b4ec", self.text)
        args_block = self.text.split("VLLM_ARGS=(", 1)[1].split(")", 1)[0]
        self.assertNotIn("--enforce-eager", args_block)
        self.assertIn("refuse_enforce_eager", self.text)
        self.assertIn("This script does not download", self.text)

    def test_x86_without_override_is_refused(self):
        result = _run_script({}, "--dry-run")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("ARM64", combined)

    def test_dry_run_on_override_prints_mtp_side_port_command(self):
        result = _run_script({"SPARK_B_OK": "1", "ENGINE": "native"}, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("DRY_RUN_CMD:", out)
        self.assertIn("--port 18091", out)
        self.assertIn("--kv-cache-dtype fp8", out)
        self.assertIn("--enable-prefix-caching", out)
        self.assertIn("num_speculative_tokens=3", out)
        self.assertIn("--speculative-config", out)
        self.assertIn("mtp", out)
        self.assertNotIn("--enforce-eager", out.split("DRY_RUN_CMD:", 1)[-1])
        self.assertNotIn("--port 18090", out)
        self.assertIn("18090", out)  # rollback mention only

    def test_stock_nvidia_checkpoint_is_refused(self):
        result = _run_script(
            {"SPARK_B_OK": "1", "MODEL": STOCK, "ENGINE": "native"},
            "--dry-run",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("abliterated", result.stderr.lower())

    def test_binding_rollback_port_is_refused(self):
        result = _run_script(
            {"SPARK_B_OK": "1", "SERVE_PORT": "18090", "ENGINE": "native"},
            "--dry-run",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("18091", result.stderr)

    def test_enforce_eager_extra_args_are_refused(self):
        result = _run_script(
            {
                "SPARK_B_OK": "1",
                "ENGINE": "native",
                "EXTRA_VLLM_ARGS": "--enforce-eager",
            },
            "--dry-run",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("enforce-eager", result.stderr)


class RunbookChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RUNBOOK.read_text(encoding="utf-8")

    def test_download_smoke_rollback_and_post_cutover_guard(self):
        self.assertIn("spark-b4ec", self.text)
        self.assertIn("never on dell", self.text.lower())
        self.assertIn("/v1/models", self.text)
        self.assertIn("chat/completions", self.text)
        self.assertIn("100.92.253.61:18091", self.text)
        self.assertIn("100.92.253.61:18090", self.text)
        self.assertIn("Keep `:18090`", self.text)
        self.assertIn(PREFERRED, self.text)
        self.assertIn(STOCK, self.text)
        self.assertIn("Do **not** use", self.text)
        self.assertIn("LOCAL_LITELLM_MASTER_KEY", self.text)
        self.assertIn("allow_requests_on_db_unavailable", self.text)
        self.assertIn(POST_CUTOVER, self.text)
        self.assertIn("Do not point `local-primary` at Spark B `:18091`", self.text)
        self.assertNotIn("hf download nvidia/Qwen3.6-35B-A3B-NVFP4", self.text)


if __name__ == "__main__":
    unittest.main()
