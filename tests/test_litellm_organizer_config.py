from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "litellm" / "config.yaml"


class LiteLLMOrganizerConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CONFIG.read_text(encoding="utf-8")

    def test_spark_aliases_and_no_paid_hosts(self):
        self.assertIn("model_name: local-driver", self.text)
        self.assertIn("model_name: local-coder", self.text)
        self.assertIn("100.92.253.61:18090", self.text)
        self.assertIn("100.111.220.1:18082", self.text)
        lowered = self.text.lower()
        for needle in ("api.openai.com", "api.anthropic.com", "api.x.ai"):
            self.assertNotIn(needle, lowered)

    def test_master_key_from_env_and_db_unavailable_is_allowed(self):
        self.assertIn("master_key: os.environ/LITELLM_MASTER_KEY", self.text)
        self.assertIn("allow_requests_on_db_unavailable: true", self.text)
        self.assertIn("background_health_checks: false", self.text)

    def test_langfuse_otel_callback_is_wired(self):
        self.assertIn('callbacks: ["langfuse_otel"]', self.text)
        self.assertNotRegex(self.text, r"(?m)^\s*success_callback:")


if __name__ == "__main__":
    unittest.main()
