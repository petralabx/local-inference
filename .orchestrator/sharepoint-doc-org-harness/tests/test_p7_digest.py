from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.config import PACKAGE_ROOT, HarnessConfig, load_config
from harness.identity import content_hash
from harness.jobs.digest import DigestReport, run_digest
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger, DocumentRecord


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


def test_digest_skips_ledger_hash_without_rule(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    src = inbox / "random-memo.pdf"
    src.write_bytes(b"no-rule-bytes")
    digest = content_hash(src)
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    ledger = DocumentLedger(Path(cfg.journal_path))
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title="Already Filed",
            prefix="GEN",
            doc_type="GEN",
            doc_date="2026-08-19",
            version=1,
            home="04_Admin",
            current_path=str(root / "04_Admin" / "filed.pdf"),
            source="relabel_parse",
        )
    )
    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest-skip.json",
        llm_caller=lambda **_: (
            '{"prefix":"GEN","target_folder":"02_Business_Ops",'
            '"description":"must-not-move","confidence":0.9}'
        ),
    )
    assert report.skipped >= 1
    assert report.moved == 0
    assert src.exists()
    assert not (root / "02_Business_Ops").exists() or not list((root / "02_Business_Ops").rglob("*"))
    journal.close()
    ledger.close()


def test_digest_rule_hit_moves_despite_ledger_hash(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    capture = root / "00_Inbox" / "_from_desktop"
    capture.mkdir(parents=True)
    src = capture / "trafilea-po.pdf"
    src.write_bytes(b"leftover-po")
    digest = content_hash(src)
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    ledger = DocumentLedger(Path(cfg.journal_path))
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title="Already Hashed Trafilea",
            prefix="PRO",
            doc_type="PRO",
            doc_date="2026-08-19",
            version=1,
            home="01_Clients_Projects",
            current_path=str(root / "01_Clients_Projects" / "Trafilea" / "filed.pdf"),
            source="relabel_parse",
        )
    )
    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest-rehome.json",
        llm_caller=lambda **_: '{"error":"rule hit must not call llm"}',
        only=["_from_desktop"],
    )
    target = root / "01_Clients_Projects" / "Trafilea"
    assert report.moved >= 1
    assert not src.exists()
    assert list(target.glob("*.pdf"))
    journal.close()
    ledger.close()
