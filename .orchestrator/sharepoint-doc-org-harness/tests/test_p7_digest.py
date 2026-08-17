from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.config import PACKAGE_ROOT, HarnessConfig, load_config
from harness.jobs.digest import DigestReport, run_digest
from harness.journal.store import ActionJournal


def _cfg_for_root(tmp_path: Path, root: Path) -> HarnessConfig:
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p)


def test_paid_url_guard_on_digest_config(tmp_path: Path) -> None:
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["litellm"]["base_url"] = "https://api.anthropic.com/v1"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        load_config(p)


def test_digest_dry_run_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    (inbox / "a.txt").write_text("x", encoding="utf-8")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report_path = tmp_path / "reports" / "digest.json"
    report = run_digest(cfg=cfg, journal=journal, report_path=report_path, dry_run=True)
    assert report_path.exists()
    assert report.inbox_active == 1
    assert "dry_run" in report.notes
    assert not report.ceiling_breach
    journal.close()


def test_digest_moves_via_correction_rule(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    (inbox / "trafilea-po.pdf").write_bytes(b"po")
    cfg = _cfg_for_root(tmp_path, root)
    # Point correction rules at package defaults
    journal = ActionJournal(Path(cfg.journal_path) if Path(cfg.journal_path).is_absolute() else tmp_path / "j.sqlite3")
    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest.json",
        llm_caller=lambda **_: '{"error":"should not call"}',
    )
    assert isinstance(report, DigestReport)
    assert report.moved >= 1
    assert report.inbox_scanned >= 1
    journal.close()


def test_digest_scans_mail_and_nested_capture_not_inbox_trees(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    mail = inbox / "_from_mail"
    desktop = inbox / "_from_desktop" / "nested"
    hidden = inbox / ".cursor"
    mail.mkdir(parents=True)
    desktop.mkdir(parents=True)
    hidden.mkdir(parents=True)
    (mail / "note.pdf").write_bytes(b"note")
    (mail / "clawdbot.pem").write_text("secret", encoding="utf-8")
    (desktop / "trafilea-po.pdf").write_bytes(b"po")
    (hidden / "should-not-scan.txt").write_text("no", encoding="utf-8")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest-mail.json",
        llm_caller=lambda **_: (
            '{"prefix":"GEN","target_folder":"00_Inbox/_Unsorted_Imports",'
            '"description":"x","confidence":0.8}'
        ),
        only=["_from_mail", "_from_desktop"],
        limit=10,
    )
    assert report.inbox_scanned == 3
    assert report.skipped >= 1
    assert (mail / "clawdbot.pem").exists()
    assert (hidden / "should-not-scan.txt").exists()
    assert report.moved >= 1
    journal.close()
