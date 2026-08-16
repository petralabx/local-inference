from __future__ import annotations

from harness.config import PACKAGE_ROOT, load_config


def test_cutover_execute_checklist_names_live_gates() -> None:
    text = (PACKAGE_ROOT / "docs" / "execute-checklist.md").read_text(encoding="utf-8")
    for needle in (
        "Five-file smoke",
        "VTA redirect",
        "taylorvalton",
        "drain",
        "90 days",
        "06:00",
        "Petra",
    ):
        assert needle in text


def test_cutover_locked_defaults_still_load() -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert cfg.litellm.classify_model == "local-driver"
    assert cfg.auto_archive is False
    assert cfg.inbox_active_ceiling == 0
    assert cfg.mail_lookback_days == 90
