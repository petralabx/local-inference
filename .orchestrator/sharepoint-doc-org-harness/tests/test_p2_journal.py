from __future__ import annotations

from pathlib import Path

from harness.cli.main import main
from harness.identity import content_hash, file_identity
from harness.journal.store import ActionJournal, apply_move, reverse_actions


def test_content_hash_stable(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    h1 = content_hash(p)
    h2 = content_hash(p)
    assert h1 == h2
    assert len(h1) == 64
    ident = file_identity(p)
    assert ident["sha256"] == h1
    assert ident["size"] == 5


def test_move_journal_and_reverse(tmp_path: Path) -> None:
    src = tmp_path / "inbox" / "doc.pdf"
    dest = tmp_path / "clients" / "doc.pdf"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"%PDF-fixture")
    digest = content_hash(src)

    journal = ActionJournal(tmp_path / "journal.sqlite3")
    run_id = journal.start_run(note="fixture-move")
    apply_move(src, dest)
    journal.record(
        run_id,
        "move",
        {"from": str(src), "to": str(dest), "sha256": digest},
    )

    assert not src.exists()
    assert dest.exists()

    n = reverse_actions(journal, run_id)
    assert n == 1
    assert src.exists()
    assert not dest.exists()
    assert content_hash(src) == digest
    journal.close()


def test_cli_reverse(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    dest = tmp_path / "b.txt"
    src.write_text("x", encoding="utf-8")
    journal_path = tmp_path / "j.sqlite3"
    journal = ActionJournal(journal_path)
    run_id = journal.start_run()
    apply_move(src, dest)
    journal.record(run_id, "move", {"from": str(src), "to": str(dest), "sha256": content_hash(dest)})
    journal.close()

    rc = main(["reverse", "--run-id", run_id, "--journal", str(journal_path)])
    assert rc == 0
    assert src.exists()
    assert not dest.exists()
