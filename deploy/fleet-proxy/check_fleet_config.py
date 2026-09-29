#!/usr/bin/env python3
"""Check the fleet proxy config (litellm/fleet.yaml) against the P1 rules.

The litellm-fleet unit runs this before every start, so a bad config stops
the fleet proxy instead of serving. Rules:

- Every alias uses a D11 cloud provider and reads its key from
  os.environ/<PROVIDER>_API_KEY. No api_base, so no local backend (P1b
  changes this rule when it adds local-primary and local-fast).
- No local-driver or local-coder alias, ever (D23, SC-13).
- Each D11 provider has at least two aliases (a strong and a fast one).
- No trace callback (F37).
- The master key and the database URL come from the environment.
- allow_requests_on_db_unavailable is absent or false (fail closed).
- With --bind-host, the address is a tailnet (100.64.0.0/10) IPv4 address.

Usage:
    python check_fleet_config.py /opt/litellm-fleet/fleet.yaml [--bind-host 100.x.y.z]

Exit codes: 0 clean, 1 a rule failed, 2 the file cannot be read.
"""

from __future__ import annotations

import argparse
import ipaddress
import sys
from collections import Counter
from pathlib import Path

import yaml

# D11 providers, keyed by LiteLLM's model prefix, with the env var for the key.
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
FORBIDDEN_ALIASES = {"local-driver", "local-coder"}
CALLBACK_KEYS = ("callbacks", "success_callback", "failure_callback", "service_callback")
TAILNET = ipaddress.ip_network("100.64.0.0/10")


def check_config(config: object) -> list[str]:
    """Return one message per broken rule. An empty list means the config is clean."""
    if not isinstance(config, dict):
        return ["the config is not a mapping"]
    errors: list[str] = []

    models = config.get("model_list")
    if not isinstance(models, list) or not models:
        return errors + ["model_list is missing or empty"]

    per_provider: Counter[str] = Counter()
    names: Counter[str] = Counter()
    for index, entry in enumerate(models):
        where = f"model_list[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} is not a mapping")
            continue
        name = entry.get("model_name")
        params = entry.get("litellm_params")
        if not isinstance(name, str) or not name:
            errors.append(f"{where} has no model_name")
            continue
        names[name] += 1
        where = f"alias {name}"
        if name in FORBIDDEN_ALIASES:
            errors.append(f"{where} is forbidden on the fleet proxy (D23)")
        if name.startswith("local-"):
            errors.append(f"{where} is a local alias; P1 serves cloud aliases only")
        if not isinstance(params, dict):
            errors.append(f"{where} has no litellm_params")
            continue
        model = params.get("model")
        provider = model.split("/", 1)[0] if isinstance(model, str) and "/" in model else None
        if provider not in PROVIDER_KEYS:
            errors.append(f"{where} uses model {model!r}, which is not a D11 provider")
            continue
        per_provider[provider] += 1
        expected_key = f"os.environ/{PROVIDER_KEYS[provider]}"
        if params.get("api_key") != expected_key:
            errors.append(f"{where} must read its key as {expected_key}")
        if "api_base" in params:
            errors.append(f"{where} sets api_base; cloud aliases use the provider default")

    for name, count in names.items():
        if count > 1:
            errors.append(f"alias {name} appears {count} times")
    for provider in PROVIDER_KEYS:
        if per_provider[provider] < 2:
            errors.append(f"provider {provider} needs a strong and a fast alias")

    litellm_settings = config.get("litellm_settings") or {}
    if not isinstance(litellm_settings, dict):
        errors.append("litellm_settings is not a mapping")
        litellm_settings = {}
    for key in CALLBACK_KEYS:
        if litellm_settings.get(key):
            errors.append(f"litellm_settings.{key} is set; the fleet sends no traces")

    general = config.get("general_settings") or {}
    if not isinstance(general, dict):
        errors.append("general_settings is not a mapping")
        general = {}
    if general.get("master_key") != "os.environ/FLEET_LITELLM_MASTER_KEY":
        errors.append("general_settings.master_key must be os.environ/FLEET_LITELLM_MASTER_KEY")
    if general.get("database_url") != "os.environ/DATABASE_URL":
        errors.append("general_settings.database_url must be os.environ/DATABASE_URL")
    if general.get("allow_requests_on_db_unavailable", False) is not False:
        errors.append("general_settings.allow_requests_on_db_unavailable must be false")

    return errors


def check_bind_host(host: str) -> list[str]:
    """The proxy binds one tailnet address, never 0.0.0.0, loopback or a LAN address."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return [f"bind host {host!r} is not an IP address"]
    if address.version != 4 or address not in TAILNET:
        return [f"bind host {host} is not a tailnet address (100.64.0.0/10)"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--bind-host", help="address the unit passes to --host")
    args = parser.parse_args(argv)

    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"fleet config: cannot read {args.config}: {exc}", file=sys.stderr)
        return 2

    errors = check_config(config)
    if args.bind_host is not None:
        errors += check_bind_host(args.bind_host)
    for message in errors:
        print(f"fleet config: {message}", file=sys.stderr)
    if errors:
        return 1
    print(f"fleet config OK: {len(config['model_list'])} cloud aliases in {args.config}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
