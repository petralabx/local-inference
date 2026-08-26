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
    classify_model: str = "local-driver"
    fallback_model: str = "local-coder"
    forbid_host_substrings: list[str] = Field(default_factory=list)

    @field_validator("base_url")
    @classmethod
    def reject_paid_hosts(cls, v: str, info: Any) -> str:
        # Host check uses forbid list from the same model when available.
        return v


# Microsoft Graph Command Line Tools — first-party public client. Delegated
# only (ADR 0026). Never an app-only secret.
GRAPH_PUBLIC_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
GRAPH_DEFAULT_SITE_URL = "https://petrasoap.sharepoint.com/sites/VincePersonal"
GRAPH_DEFAULT_UPN = "vince@petrasoap.com"


class GraphConfig(BaseModel):
    """Delegated Graph surface for Vince Personal list-item stamps."""

    enabled: bool = True
    site_url: str = GRAPH_DEFAULT_SITE_URL
    library: str = "Documents"
    tenant_id: str = "organizations"
    client_id: str = GRAPH_PUBLIC_CLIENT_ID
    cache_path: str = "data/msal_graph_cache.bin"
    upn: str = GRAPH_DEFAULT_UPN


class HarnessConfig(BaseModel):
    sharepoint_sync_root: str
    inbox_rel: str = "00_Inbox"
    unsorted_rel: str = "00_Inbox/_Unsorted_Imports"
    retry_rel: str = "00_Inbox/_Retry_Imports"
    capture_from_desktop_rel: str = "00_Inbox/_from_desktop"
    capture_from_documents_rel: str = "00_Inbox/_from_documents"
    capture_from_downloads_rel: str = "00_Inbox/_from_downloads"
    capture_from_mail_rel: str = "00_Inbox/_from_mail"
    litellm: LiteLLMConfig
    horizon_days: int = 365
    auto_archive: bool = False
    inbox_active_ceiling: int = 0
    naming_mode: str = "organizer"
    mail_lookback_days: int = 90
    mail_remainder_after_proof: bool = True
    drain_map_path: str = "config/drain_map.yaml"
    delete_duplicates: bool = False
    exclude_globs: list[str] = Field(default_factory=list)
    skip_code_path_tokens: list[str] = Field(
        default_factory=lambda: ["local-inference-canonical"]
    )
    journal_path: str = "data/journal.sqlite3"
    taxonomy_path: str = "config/taxonomy_prefixes.yaml"
    correction_rules_path: str = "config/correction_rules.json"
    graph: GraphConfig = Field(default_factory=GraphConfig)

    @property
    def ceiling_enabled(self) -> bool:
        return self.inbox_active_ceiling > 0

    @property
    def readable_names(self) -> bool:
        return self.naming_mode == "readable"

    @property
    def organizer_names(self) -> bool:
        return self.naming_mode == "organizer"

    def capture_rels(self) -> list[str]:
        return [
            self.capture_from_desktop_rel,
            self.capture_from_documents_rel,
            self.capture_from_downloads_rel,
            self.capture_from_mail_rel,
        ]

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
