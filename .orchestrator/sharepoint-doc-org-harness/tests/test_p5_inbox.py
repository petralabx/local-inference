from __future__ import annotations

from pathlib import Path

from harness.actions.inbox import InboxSorter
from harness.dedupe.fclones_wrap import apply_duplicate_plan, plan_from_hash_map
from harness.identity import content_hash
from harness.journal.store import ActionJournal


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

    # Recreate same content in inbox — second run must skip via manifest
    src2 = inbox / "trafilea-order-again.pdf"
    src2.write_bytes(b"pdf-bytes")
    assert content_hash(src2) == digest
    r2 = sorter.process_file(src2, run_id=run_id)
    assert r2.status == "skipped"
    assert src2.exists(), "idempotent skip leaves file for manual triage"
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
