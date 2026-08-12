from __future__ import annotations

from pathlib import Path

import yaml

from harness.config import PACKAGE_ROOT, load_config
from harness.jobs.digest import run_digest
from harness.journal.store import ActionJournal, reverse_actions
from harness.mail.graph_client import AttachmentMeta, FakeGraphMailClient
from harness.mail.pipeline import MailIngestPipeline
from harness.provenance.query import ProvenanceStore


def test_p8_end_to_end_fixture_pipeline(tmp_path: Path) -> None:
    """Mail ingest → inbox digest move → provenance → reverse."""
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)

    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(cfg_path)

    journal = ActionJournal(tmp_path / "j.sqlite3")
    mail_run = journal.start_run(note="mail")
    client = FakeGraphMailClient(
        messages={
            "m1": [
                AttachmentMeta(
                    "m1",
                    "a1",
                    "trafilea-invoice.pdf",
                    b"invoice-bytes",
                    "application/pdf",
                )
            ]
        }
    )
    pipe = MailIngestPipeline(client=client, journal=journal, target_dir=inbox)
    mail_results = pipe.ingest_once(run_id=mail_run)
    assert mail_results[0].status == "saved"
    assert (inbox / "trafilea-invoice.pdf").exists() or any(inbox.glob("trafilea*"))

    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest.json",
        llm_caller=lambda **_: '{"prefix":"MISC","target_folder":"06_Reference","confidence":0.1}',
    )
    assert report.moved >= 1

    store = ProvenanceStore.from_journal(journal)
    hits = store.lookup(name="trafilea")
    assert hits, "provenance should see trafilea path trail"

    # Reverse digest moves (latest run_id on report)
    n = reverse_actions(journal, report.run_id)
    assert n >= 1
    journal.close()


def test_p8_docs_present() -> None:
    docs = PACKAGE_ROOT / "docs"
    assert (docs / "ops.md").is_file()
    assert (docs / "oss-stack.md").is_file()
    assert (docs / "cutover-checklist.md").is_file()
