"""Unit tests for deploy/fleet-proxy/check_fleet_config.py (agent fleet spec P1).

Run from the repository root (needs PyYAML):
    python -m unittest discover -s deploy/fleet-proxy/tests -v
"""

from __future__ import annotations

import copy
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

FLEET_PROXY_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = FLEET_PROXY_DIR.parents[1]
FLEET_YAML = REPO_ROOT / "litellm" / "fleet.yaml"

_spec = importlib.util.spec_from_file_location("check_fleet_config", FLEET_PROXY_DIR / "check_fleet_config.py")
check_fleet_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_fleet_config)


def load_fleet() -> dict:
    return yaml.safe_load(FLEET_YAML.read_text(encoding="utf-8"))


def alias(config: dict, name: str) -> dict:
    return next(entry for entry in config["model_list"] if entry["model_name"] == name)


class FleetYamlTests(unittest.TestCase):
    def test_fleet_yaml_is_clean(self):
        self.assertEqual(check_fleet_config.check_config(load_fleet()), [])

    def test_every_alias_is_cloud(self):
        names = [entry["model_name"] for entry in load_fleet()["model_list"]]
        self.assertEqual(len(names), 14)
        self.assertTrue(all(name.startswith("cloud-") for name in names))

    def test_fleet_yaml_sets_the_fail_closed_settings(self):
        general = load_fleet()["general_settings"]
        self.assertIs(general["allow_requests_on_db_unavailable"], False)
        self.assertIs(general["store_model_in_db"], False)
        self.assertIs(general["store_prompts_in_spend_logs"], False)

    def test_main_accepts_fleet_yaml_and_a_tailnet_host(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_fleet_config.main([str(FLEET_YAML), "--bind-host", "100.101.102.103"])
        self.assertEqual(code, 0)
        self.assertIn("14 cloud aliases", out.getvalue())


class ConfigRuleTests(unittest.TestCase):
    """Each case breaks one rule in a copy of fleet.yaml and expects one message."""

    def assert_refused(self, config: dict, fragment: str) -> None:
        errors = check_fleet_config.check_config(config)
        self.assertTrue(any(fragment in error for error in errors), f"{fragment!r} not in {errors}")

    def setUp(self):
        self.config = copy.deepcopy(load_fleet())

    def test_local_driver_alias(self):
        self.config["model_list"].append(
            {"model_name": "local-driver", "litellm_params": {"model": "openai/x", "api_key": "os.environ/OPENAI_API_KEY"}}
        )
        self.assert_refused(self.config, "alias local-driver is forbidden on the fleet proxy (D23)")

    def test_local_coder_alias(self):
        self.config["model_list"].append(
            {"model_name": "local-coder", "litellm_params": {"model": "openai/x", "api_key": "os.environ/OPENAI_API_KEY"}}
        )
        self.assert_refused(self.config, "alias local-coder is forbidden on the fleet proxy (D23)")

    def test_other_local_alias(self):
        self.config["model_list"].append(
            {"model_name": "local-primary", "litellm_params": {"model": "openai/x", "api_key": "os.environ/OPENAI_API_KEY"}}
        )
        self.assert_refused(self.config, "alias local-primary is a local alias; P1 serves cloud aliases only")

    def test_literal_api_key(self):
        alias(self.config, "cloud-claude-sonnet")["litellm_params"]["api_key"] = "sk-ant-literal"
        self.assert_refused(self.config, "alias cloud-claude-sonnet must read its key as os.environ/ANTHROPIC_API_KEY")

    def test_wrong_provider_env_var(self):
        alias(self.config, "cloud-claude-sonnet")["litellm_params"]["api_key"] = "os.environ/OPENAI_API_KEY"
        self.assert_refused(self.config, "alias cloud-claude-sonnet must read its key as os.environ/ANTHROPIC_API_KEY")

    def test_api_base_on_a_cloud_alias(self):
        alias(self.config, "cloud-gpt")["litellm_params"]["api_base"] = "http://127.0.0.1:8000/v1"
        self.assert_refused(self.config, "alias cloud-gpt sets api_base")

    def test_non_d11_provider(self):
        self.config["model_list"].append(
            {"model_name": "cloud-bedrock", "litellm_params": {"model": "bedrock/x", "api_key": "os.environ/X"}}
        )
        self.assert_refused(self.config, "alias cloud-bedrock uses model 'bedrock/x', which is not a D11 provider")

    def test_provider_with_one_alias(self):
        self.config["model_list"] = [e for e in self.config["model_list"] if e["model_name"] != "cloud-grok-fast"]
        self.assert_refused(self.config, "provider xai needs a strong and a fast alias")

    def test_duplicate_alias(self):
        self.config["model_list"].append(copy.deepcopy(alias(self.config, "cloud-claude-sonnet")))
        self.assert_refused(self.config, "alias cloud-claude-sonnet appears 2 times")

    def test_trace_callbacks(self):
        for key in ("callbacks", "success_callback", "failure_callback", "service_callback"):
            with self.subTest(key=key):
                config = copy.deepcopy(self.config)
                config["litellm_settings"][key] = ["langfuse_otel"]
                self.assert_refused(config, f"litellm_settings.{key} is set; the fleet sends no traces")

    def test_allow_requests_on_db_unavailable(self):
        self.config["general_settings"]["allow_requests_on_db_unavailable"] = True
        self.assert_refused(self.config, "allow_requests_on_db_unavailable must be false")

    def test_store_model_in_db(self):
        self.config["general_settings"]["store_model_in_db"] = True
        self.assert_refused(self.config, "store_model_in_db must be false")

    def test_environment_variables_block(self):
        self.config["environment_variables"] = {"LANGFUSE_HOST": "https://cloud.langfuse.com"}
        self.assert_refused(self.config, "environment_variables is set")

    def test_literal_master_key(self):
        self.config["general_settings"]["master_key"] = "sk-literal"
        self.assert_refused(self.config, "master_key must be os.environ/FLEET_LITELLM_MASTER_KEY")

    def test_trading_master_key_var(self):
        self.config["general_settings"]["master_key"] = "os.environ/LITELLM_MASTER_KEY"
        self.assert_refused(self.config, "master_key must be os.environ/FLEET_LITELLM_MASTER_KEY")

    def test_literal_database_url(self):
        self.config["general_settings"]["database_url"] = "postgresql://u:p@127.0.0.1/litellm_fleet"
        self.assert_refused(self.config, "database_url must be os.environ/DATABASE_URL")

    def test_not_a_mapping(self):
        self.assertEqual(check_fleet_config.check_config(["x"]), ["the config is not a mapping"])

    def test_empty_model_list(self):
        self.config["model_list"] = []
        self.assert_refused(self.config, "model_list is missing or empty")


class BindHostTests(unittest.TestCase):
    def test_tailnet_addresses_pass(self):
        for host in ("100.64.0.1", "100.101.102.103", "100.127.255.254"):
            with self.subTest(host=host):
                self.assertEqual(check_fleet_config.check_bind_host(host), [])

    def test_other_addresses_fail(self):
        for host in ("", "0.0.0.0", "127.0.0.1", "192.168.1.5", "100.128.0.1", "fd7a:115c:a1e0::1", "fleet-proxy"):
            with self.subTest(host=host):
                self.assertNotEqual(check_fleet_config.check_bind_host(host), [])


class MainExitCodeTests(unittest.TestCase):
    def run_main(self, text: str, *extra: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet.yaml"
            path.write_text(text, encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return check_fleet_config.main([str(path), *extra])

    def test_rule_failure_exits_1(self):
        config = load_fleet()
        config["general_settings"]["allow_requests_on_db_unavailable"] = True
        self.assertEqual(self.run_main(yaml.safe_dump(config)), 1)

    def test_bad_bind_host_exits_1(self):
        self.assertEqual(self.run_main(FLEET_YAML.read_text(encoding="utf-8"), "--bind-host", "0.0.0.0"), 1)

    def test_unreadable_yaml_exits_2(self):
        self.assertEqual(self.run_main("model_list: [\n"), 2)


if __name__ == "__main__":
    unittest.main()
