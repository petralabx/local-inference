from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.config import PACKAGE_ROOT, load_config
from harness.naming import build_readable_name, is_readable, next_free_name


def test_cutover_default_pins_spark_and_drops_ceiling() -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert cfg.litellm.base_url == "http://100.103.33.54:4000/v1"
    assert cfg.litellm.classify_model == "local-driver"
    assert cfg.litellm.fallback_model == "local-coder"
    assert cfg.inbox_active_ceiling == 0
    assert cfg.ceiling_enabled is False
    assert cfg.auto_archive is False
    assert cfg.readable_names is True
    assert cfg.capture_rels() == [
        "00_Inbox/_from_desktop",
        "00_Inbox/_from_documents",
        "00_Inbox/_from_downloads",
    ]


def test_cutover_rejects_paid_host(tmp_path: Path) -> None:
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["litellm"]["base_url"] = "https://api.openai.com/v1"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        load_config(p)


def test_cutover_readable_names_not_coded_prefix() -> None:
    name = build_readable_name(description="Dropship A1 American", ext="PDF")
    assert name == "Dropship A1 American.pdf"
    assert is_readable(name)
    assert "PRO" not in name
    assert "_v01" not in name
    bumped = next_free_name({name}, name)
    assert bumped == "Dropship A1 American-2.pdf"
