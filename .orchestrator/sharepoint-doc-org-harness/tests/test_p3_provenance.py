from __future__ import annotations

from pathlib import Path

from harness.cli.main import main
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move
from harness.provenance.query import ProvenanceStore


def test_where_resolves_renamed_path(tmp_path: Path) -> None:
    a = tmp_path / "old" / "Invoice.pdf"
    b = tmp_path / "finance" / "2026-08-12_INV_Invoice_v01.pdf"
    a.parent.mkdir(parents=True)
    a.write_bytes(b"invoice-bytes")
    digest = content_hash(a)

    journal = ActionJournal(tmp_path / "journal.sqlite3")
    run_id = journal.start_run()
    apply_move(a, b)
    journal.record(run_id, "move", {"from": str(a), "to": str(b), "sha256": digest})

    store = ProvenanceStore.from_journal(journal)
    by_path = store.lookup(path=str(a))
    assert by_path, "expected hit for prior path"
    assert by_path[0].current_path == str(b)

    by_hash = store.lookup(content_hash=digest)
    assert by_hash
    assert by_hash[0].current_path == str(b)

    by_name = store.lookup(name="Invoice.pdf")
    assert by_name
    journal.close()


def test_cli_where(tmp_path: Path) -> None:
    a = tmp_path / "x.txt"
    b = tmp_path / "y.txt"
    a.write_text("z", encoding="utf-8")
    digest = content_hash(a)
    journal_path = tmp_path / "j.sqlite3"
    journal = ActionJournal(journal_path)
    run_id = journal.start_run()
    apply_move(a, b)
    journal.record(run_id, "move", {"from": str(a), "to": str(b), "sha256": digest})
    journal.close()

    rc = main(["where", "--path", str(a), "--journal", str(journal_path)])
    assert rc == 0
