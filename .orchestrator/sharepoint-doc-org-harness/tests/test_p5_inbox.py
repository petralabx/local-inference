from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from harness.actions.archive import ArchiveLane
from harness.actions.inbox import InboxSorter
from harness.dedupe.fclones_wrap import apply_duplicate_plan, plan_from_hash_map
from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.ledger.documents import DocumentLedger, DocumentRecord


def test_inbox_move_not_copy_and_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    src = inbox / "trafilea-order.pdf"
    src.write_bytes(b"pdf-bytes")
    digest = content_hash(src)

    journal = ActionJournal(tmp_path / "j.sqlite3")
    run_id = journal.start_run()
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=[
            {
                "id": "r1",
                "keywords": ["trafilea"],
                "target_folder": "01_Clients_Projects/Trafilea",
                "prefix": "PRO",
                "confidence_boost": 2,
            }
        ],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        manifest_path=tmp_path / "manifest.json",
    )
    r1 = sorter.process_file(src, run_id=run_id)
    assert r1.status == "moved"
    assert r1.dest is not None
    assert r1.dest.exists()
    assert not src.exists(), "must move, not copy"

    r_home = sorter.process_file(r1.dest, run_id=run_id)
    assert r_home.status == "skipped"
    assert r_home.detail == "already processed hash"
    assert r1.dest.exists(), "already at the rule home stays put"

    src2 = inbox / "trafilea-order-again.pdf"
    src2.write_bytes(b"pdf-bytes")
    assert content_hash(src2) == digest
    r2 = sorter.process_file(src2, run_id=run_id)
    assert r2.status == "moved"
    assert r2.dest is not None
    assert r2.dest.parent == root / "01_Clients_Projects" / "Trafilea"
    assert not src2.exists(), "rule hit still rehomes a leftover hashed copy"
    journal.close()


def test_inbox_skips_ledger_hash_not_in_manifest(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    src = inbox / "already-filed.pdf"
    src.write_bytes(b"filed-bytes")
    digest = content_hash(src)
    journal_path = tmp_path / "j.sqlite3"
    journal = ActionJournal(journal_path)
    ledger = DocumentLedger(journal_path)
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
    run_id = journal.start_run()
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=[],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        manifest_path=tmp_path / "manifest.json",
        ledger=ledger,
        llm_caller=lambda **_: '{"error":"must not classify a ledger duplicate"}',
    )
    result = sorter.process_file(src, run_id=run_id)
    assert result.status == "skipped"
    assert result.detail == "already in ledger"
    assert src.exists()
    journal.close()


def test_rule_hit_with_ledger_hash_still_moves(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    capture = root / "00_Inbox" / "_from_desktop"
    capture.mkdir(parents=True)
    src = capture / "trafilea-order.pdf"
    src.write_bytes(b"leftover-capture")
    digest = content_hash(src)
    journal_path = tmp_path / "j.sqlite3"
    journal = ActionJournal(journal_path)
    ledger = DocumentLedger(journal_path)
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title="Already Filed Trafilea",
            prefix="PRO",
            doc_type="PRO",
            doc_date="2026-08-19",
            version=1,
            home="01_Clients_Projects",
            current_path=str(root / "01_Clients_Projects" / "Trafilea" / "filed.pdf"),
            source="relabel_parse",
        )
    )
    run_id = journal.start_run()
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=[
            {
                "id": "r1",
                "keywords": ["trafilea"],
                "target_folder": "01_Clients_Projects/Trafilea",
                "prefix": "PRO",
                "confidence_boost": 2,
            }
        ],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        manifest_path=tmp_path / "manifest.json",
        ledger=ledger,
        llm_caller=lambda **_: '{"error":"rule hit must not call llm"}',
    )
    result = sorter.process_file(src, run_id=run_id)
    assert result.status == "moved"
    assert result.dest is not None
    assert result.dest.parent == root / "01_Clients_Projects" / "Trafilea"
    assert not src.exists()
    journal.close()


def test_dedupe_tombstone_default(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    digest = content_hash(a)
    groups = plan_from_hash_map({digest: [a, b]})
    recorded: list[tuple[str, dict]] = []

    def rec(action_type: str, payload: dict) -> None:
        recorded.append((action_type, payload))

    actions = apply_duplicate_plan(groups, delete_duplicates=False, journal_record=rec)
    assert actions[0]["action"] == "tombstone"
    assert a.exists() and b.exists()
    assert recorded[0][0] == "tombstone"


def test_archive_in_place_beyond_horizon(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    folder = root / "01_Clients_Projects"
    folder.mkdir(parents=True)
    old = folder / "old-doc.pdf"
    old.write_bytes(b"old")
    past = datetime.now(timezone.utc) - timedelta(days=400)
    ts = past.timestamp()
    os.utime(old, (ts, ts))

    journal = ActionJournal(tmp_path / "j.sqlite3")
    run_id = journal.start_run()
    lane = ArchiveLane(root=root, journal=journal, horizon_days=365)
    assert lane.should_archive(old)
    r = lane.archive_file(old, run_id=run_id)
    assert r.status == "archived"
    assert r.dest is not None
    assert r.dest.exists()
    assert not old.exists()
    assert "_Archive" in r.dest.parts
    journal.close()
