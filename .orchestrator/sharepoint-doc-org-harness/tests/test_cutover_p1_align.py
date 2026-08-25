from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from harness.config import PACKAGE_ROOT, load_config
from harness.naming import (
    build_organizer_name,
    build_readable_name,
    is_organizer_name,
    is_readable,
    next_free_name,
    next_organizer_version,
)


def test_cutover_default_pins_spark_and_drops_ceiling() -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert cfg.litellm.base_url == "http://100.103.33.54:4000/v1"
    assert cfg.litellm.classify_model == "local-driver"
    assert cfg.litellm.fallback_model == "local-coder"
    assert cfg.inbox_active_ceiling == 0
    assert cfg.ceiling_enabled is False
    assert cfg.auto_archive is False
    assert cfg.naming_mode == "organizer"
    assert cfg.organizer_names is True
    assert cfg.readable_names is False
    assert cfg.capture_rels() == [
        "00_Inbox/_from_desktop",
        "00_Inbox/_from_documents",
        "00_Inbox/_from_downloads",
        "00_Inbox/_from_mail",
    ]


def test_cutover_rejects_paid_host(tmp_path: Path) -> None:
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["litellm"]["base_url"] = "https://api.openai.com/v1"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        load_config(p)


def test_cutover_organizer_name_law() -> None:
    name = build_organizer_name(
        when=date(2026, 8, 18),
        prefix="inv",
        title="Happy Yards Quote",
        ext="PDF",
    )
    assert name == "2026-08-18_INV_Happy Yards Quote_v01.pdf"
    assert is_organizer_name(name)
    bumped = next_organizer_version({name}, name)
    assert bumped == "2026-08-18_INV_Happy Yards Quote_v02.pdf"


def test_cutover_organizer_peels_stacked_happy_yards_name() -> None:
    stacked = (
        "2026-08-18_INV_2026-08-18_01_CLIENTS_PROJECTS_"
        "Happy Yards Garden Clean Up Quote_v01_v01.pdf"
    )
    assert not is_organizer_name(stacked)
    peeled = build_organizer_name(
        when=date(2026, 8, 18),
        prefix="INV",
        title=stacked,
        ext="pdf",
    )
    assert peeled == "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
    assert is_organizer_name(peeled)
    # Passing an already-law stem as the title must not wrap a second time.
    again = build_organizer_name(
        when=date(2026, 8, 18),
        prefix="INV",
        title="2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01",
        ext="pdf",
    )
    assert again == peeled


def test_cutover_organizer_keeps_date_in_middle_of_words() -> None:
    title = "Notes from 2026-08-18 meeting"
    name = build_organizer_name(
        when=date(2026, 8, 18),
        prefix="MTG",
        title=title,
        ext="pdf",
    )
    assert name == "2026-08-18_MTG_Notes from 2026-08-18 meeting_v01.pdf"
    assert is_organizer_name(name)
    glued = build_organizer_name(
        when=date(2026, 8, 18),
        prefix="FIN",
        title="FY2026-08-18Budget Review",
        ext="pdf",
    )
    assert glued == "2026-08-18_FIN_FY2026-08-18Budget Review_v01.pdf"
    assert is_organizer_name(glued)


def test_cutover_readable_helper_still_exists() -> None:
    name = build_readable_name(description="Dropship A1 American", ext="PDF")
    assert name == "Dropship A1 American.pdf"
    assert is_readable(name)
    bumped = next_free_name({name}, name)
    assert bumped == "Dropship A1 American-2.pdf"
