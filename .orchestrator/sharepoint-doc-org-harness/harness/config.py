from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "default.yaml"


class LiteLLMConfig(BaseModel):
    base_url: str
    classify_model: str = "local-fast"
    fallback_model: str = "local-primary"
    forbid_host_substrings: list[str] = Field(default_factory=list)

    @field_validator("base_url")
    @classmethod
    def reject_paid_hosts(cls, v: str, info: Any) -> str:
        # Host check uses forbid list from the same model when available.
        return v


class HarnessConfig(BaseModel):
    sharepoint_sync_root: str
    inbox_rel: str = "00_Inbox"
    unsorted_rel: str = "00_Inbox/_Unsorted_Imports"
    retry_rel: str = "00_Inbox/_Retry_Imports"
    litellm: LiteLLMConfig
    horizon_days: int = 365
    inbox_active_ceiling: int = 100
    delete_duplicates: bool = False
    exclude_globs: list[str] = Field(default_factory=list)
    journal_path: str = "data/journal.sqlite3"
    taxonomy_path: str = "config/taxonomy_prefixes.yaml"
    correction_rules_path: str = "config/correction_rules.json"

    def validate_inference_policy(self) -> None:
        base = self.litellm.base_url.lower()
        for needle in self.litellm.forbid_host_substrings:
            if needle.lower() in base:
                raise ValueError(
                    f"Paid/cloud inference host forbidden in litellm.base_url: {needle}"
                )

    @property
    def sync_root(self) -> Path:
        return Path(self.sharepoint_sync_root)

    def resolve_path(self, rel: str) -> Path:
        p = Path(rel)
        if p.is_absolute():
            return p
        return PACKAGE_ROOT / p


def load_config(path: Path | None = None) -> HarnessConfig:
    cfg_path = path or Path(
        __import__("os").environ.get("HARNESS_CONFIG", str(DEFAULT_CONFIG_PATH))
    )
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    cfg = HarnessConfig.model_validate(raw)
    cfg.validate_inference_policy()
    return cfg


def load_taxonomy(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prefixes = data.get("prefixes") or {}
    if not isinstance(prefixes, dict) or not prefixes:
        raise ValueError(f"No prefixes in taxonomy file: {path}")
    return {str(k): str(v) for k, v in prefixes.items()}


def load_correction_rules(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("rules") or []
    if not isinstance(rules, list):
        raise ValueError("correction_rules.rules must be a list")
    return rules


def match_exclude(path: Path, patterns: list[str]) -> bool:
    """Return True if path should be skipped (simple ** segment matching)."""
    s = path.as_posix().lower()
    for pat in patterns:
        p = pat.lower().replace("\\", "/")
        if p.startswith("**/") and p.endswith("/**"):
            token = p[3:-3]
            if f"/{token}/" in f"/{s}/" or s.startswith(f"{token}/"):
                return True
        elif p.startswith("**/"):
            token = p[3:]
            if s.endswith(token) or f"/{token}" in f"/{s}":
                return True
        elif token_in_path(s, p):
            return True
    return False


def token_in_path(path_s: str, pat: str) -> bool:
    return pat.strip("*") in path_s
