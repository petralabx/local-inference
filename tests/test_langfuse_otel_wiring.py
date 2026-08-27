from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "litellm" / "config.yaml"
START_PROXY = REPO_ROOT / "scripts" / "start_proxy.sh"
RESTART_PROXY = REPO_ROOT / "scripts" / "restart_litellm_proxy.ps1"
ENSURE_PROXY = REPO_ROOT / "scripts" / "ensure_proxy.sh"
GITIGNORE = REPO_ROOT / ".gitignore"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
SELF_HOSTED_HOST = "http://127.0.0.1:3100"
CLOUD_HOSTS = (
    "cloud.langfuse.com",
    "us.cloud.langfuse.com",
    "otel.langfuse.com",
)


class LangfuseOtelWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.parsed = yaml.safe_load(cls.config)
        cls.start_proxy = START_PROXY.read_text(encoding="utf-8")
        cls.restart_proxy = RESTART_PROXY.read_text(encoding="utf-8")
        cls.ensure_proxy = ENSURE_PROXY.read_text(encoding="utf-8")
        cls.gitignore = GITIGNORE.read_text(encoding="utf-8")
        cls.env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

    def test_live_config_uses_langfuse_otel_callback_only(self):
        settings = self.parsed["litellm_settings"]
        self.assertEqual(settings.get("callbacks"), ["langfuse_otel"])
        self.assertNotIn("success_callback", settings)
        self.assertNotRegex(self.config, r"(?m)^\s*success_callback:")

    def test_live_config_does_not_hardcode_langfuse_secrets_or_host(self):
        settings = self.parsed["litellm_settings"]
        general = self.parsed["general_settings"]
        for key in (
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_OTEL_HOST",
            "langfuse_public_key",
            "langfuse_secret_key",
            "langfuse_otel_host",
        ):
            self.assertNotIn(key, settings)
            self.assertNotIn(key, general)
        self.assertNotRegex(self.config, r"pk-lf-|sk-lf-")
        lowered = self.config.lower()
        for host in CLOUD_HOSTS:
            self.assertNotIn(host, lowered)

    def test_live_aliases_unchanged(self):
        self.assertIn("model_name: local-primary", self.config)
        self.assertIn("model_name: local-fast", self.config)
        self.assertIn("model_name: local-coder", self.config)
        self.assertIn("model_name: local-driver", self.config)

    def test_start_proxy_loads_langfuse_env_and_defaults_self_hosted_host(self):
        langfuse_idx = self.start_proxy.find(".env.langfuse")
        local_idx = self.start_proxy.find(".env.local")
        self.assertGreaterEqual(langfuse_idx, 0)
        self.assertGreater(local_idx, langfuse_idx)
        self.assertIn(f'LANGFUSE_OTEL_HOST:=http://127.0.0.1:3100', self.start_proxy)
        self.assertIn("export LANGFUSE_OTEL_HOST", self.start_proxy)
        for host in CLOUD_HOSTS:
            self.assertNotIn(host, self.start_proxy)

    def test_restart_proxy_loads_langfuse_env_without_printing_keys(self):
        self.assertIn("Import-LiteLlmDotEnv", self.restart_proxy)
        self.assertIn(".env.langfuse", self.restart_proxy)
        self.assertIn("LANGFUSE_OTEL_HOST", self.restart_proxy)
        self.assertIn(SELF_HOSTED_HOST, self.restart_proxy)
        self.assertNotRegex(
            self.restart_proxy,
            r"Write-Host.*LANGFUSE_(PUBLIC_KEY|SECRET_KEY|OTEL_HOST)",
        )
        for host in CLOUD_HOSTS:
            self.assertNotIn(host, self.restart_proxy)

    def test_ensure_proxy_still_starts_via_start_proxy(self):
        self.assertIn("./scripts/start_proxy.sh", self.ensure_proxy)

    def test_env_langfuse_is_gitignored(self):
        self.assertIn(".env.*", self.gitignore)
        result = subprocess.run(
            ["git", "check-ignore", "-v", ".env.langfuse"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(".env.langfuse", result.stdout)

    def test_env_example_documents_self_hosted_host_without_keys(self):
        self.assertIn("# LANGFUSE_PUBLIC_KEY=", self.env_example)
        self.assertIn("# LANGFUSE_SECRET_KEY=", self.env_example)
        self.assertIn(f"# LANGFUSE_OTEL_HOST={SELF_HOSTED_HOST}", self.env_example)
        self.assertIsNone(re.search(r"(?m)^(?!\s*#).*LANGFUSE_(PUBLIC|SECRET)_KEY=.+", self.env_example))
        self.assertNotRegex(self.env_example, r"pk-lf-|sk-lf-")
        for host in CLOUD_HOSTS:
            self.assertNotIn(host, self.env_example)


if __name__ == "__main__":
    unittest.main()
