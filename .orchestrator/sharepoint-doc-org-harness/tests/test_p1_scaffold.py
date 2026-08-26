from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from harness.config import (
    PACKAGE_ROOT,
    load_config,
    load_correction_rules,
    load_taxonomy,
    match_exclude,
)
from harness.naming import build_name, is_compliant, next_version_name


def test_default_config_loads_and_rejects_paid_host(tmp_path: Path) -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert cfg.inbox_active_ceiling == 0
    assert cfg.auto_archive is False
    assert cfg.delete_duplicates is False
    assert cfg.leftover_trees_path.endswith("leftover_trees.yaml")
    assert cfg.litellm.classify_model == "local-driver"
    assert cfg.litellm.fallback_model == "local-coder"

    bad = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    bad["litellm"]["base_url"] = "https://api.openai.com/v1"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        load_config(p)


def test_taxonomy_and_correction_rules_load() -> None:
    prefixes = load_taxonomy(PACKAGE_ROOT / "config" / "taxonomy_prefixes.yaml")
    assert "INV" in prefixes
    assert "PRO" in prefixes
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    assert len(rules) >= 5
    assert any("trafilea" in r.get("keywords", []) for r in rules)


def test_exclude_globs_skip_code_trees() -> None:
    patterns = [
        "**/node_modules/**",
        "**/.git/**",
        "**/agentic-swarm/**",
    ]
    assert match_exclude(Path("foo/node_modules/pkg/a.js"), patterns)
    assert match_exclude(Path("repos/agentic-swarm/src/x.py"), patterns)
    assert match_exclude(Path("proj/.git/config"), patterns)
    assert not match_exclude(Path("01_Clients_Projects/A1/file.pdf"), patterns)


def test_naming_convention() -> None:
    name = build_name(
        when=date(2026, 8, 12),
        prefix="pro",
        description="Dropship A1 American",
        version=1,
        ext="PDF",
    )
    assert name == "2026-08-12_PRO_DropshipA1American_v01.pdf"
    assert is_compliant(name)
    assert not is_compliant("Dropship A1 American.pdf")
    bumped = next_version_name({name}, name)
    assert bumped.endswith("_v02.pdf")
