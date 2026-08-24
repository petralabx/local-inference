from __future__ import annotations

from pathlib import Path

from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.ledger.brain import project_document
from harness.ledger.documents import DocumentLedger, DocumentRecord
from harness.actions.inbox import InboxSorter
from harness.naming import is_organizer_name


def test_document_ledger_round_trip(tmp_path: Path) -> None:
    ledger = DocumentLedger(tmp_path / "j.sqlite3")
    rec = ledger.upsert(
        DocumentRecord(
            sha256="abc",
            title="Happy Yards Quote",
            prefix="INV",
            doc_type="Invoice",
            doc_date="2026-08-18",
            version=1,
            home="01_Clients_Projects",
            current_path=r"C:\vp\01_Clients_Projects\2026-08-18_INV_Happy Yards Quote_v01.pdf",
            source="llm",
        )
    )
    got = ledger.get("abc")
    assert got is not None
    assert got.title == rec.title
    assert got.prefix == "INV"
    hits = ledger.lookup(name="Happy Yards")
    assert len(hits) == 1
    ledger.close()


def test_brain_projection_fail_open_without_key(monkeypatch) -> None:
    monkeypatch.delenv("VMC_API_KEY", raising=False)
    monkeypatch.delenv("PLX_BRAIN_API_KEY", raising=False)
    rec = DocumentRecord(
        sha256="x",
        title="t",
        prefix="GEN",
        doc_type="General",
        doc_date="2026-08-18",
        version=1,
        home="00_Inbox",
        current_path="00_Inbox/x.pdf",
        source="heuristic",
    )
    assert project_document(rec) is False


def test_relabel_keeps_current_folder(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    dest = root / "01_Clients_Projects" / "KeepMe"
    dest.mkdir(parents=True)
    src = dest / "note.pdf"
    src.write_bytes(b"keep-folder")
    journal = ActionJournal(tmp_path / "j.sqlite3")
    ledger = DocumentLedger(tmp_path / "j.sqlite3")
    run_id = journal.start_run()
    sorter = InboxSorter(
        root=root,
        journal=journal,
        rules=[],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-driver",
        forbid_host_substrings=["api.openai.com"],
        manifest_path=tmp_path / "manifest.json",
        organizer_names=True,
        ledger=ledger,
        type_by_prefix={"MEM": "Memo"},
        project_to_brain=False,
        llm_caller=lambda **_: (
            '{"prefix":"MEM","target_folder":"02_Business_Ops",'
            '"description":"note","confidence":0.9}'
        ),
    )
    result = sorter.process_file(src, run_id=run_id, ignore_manifest=True, keep_folder=True)
    assert result.status == "moved"
    assert result.dest is not None
    assert result.dest.parent == dest
    assert not (root / "02_Business_Ops").exists() or not list((root / "02_Business_Ops").glob("*"))
    journal.close()
    ledger.close()


def test_relabel_skips_recycle_bin(tmp_path: Path) -> None:
    from harness.jobs.relabel import iter_relabel_files

    root = tmp_path / "sp"
    junk = root / "00_Inbox" / "$RECYCLE.BIN" / "$RE75XIY"
    junk.mkdir(parents=True)
    (junk / "photo.jpg").write_bytes(b"junk")
    dest = root / "01_Clients_Projects"
    dest.mkdir(parents=True)
    keep = dest / "keep.pdf"
    keep.write_bytes(b"keep")
    files = iter_relabel_files(root, [])
    assert files == [keep]


def test_relabel_renames_existing_home_file(tmp_path: Path) -> None:
    from harness.config import load_config
    from harness.jobs.relabel import run_relabel
    import yaml
    from harness.config import PACKAGE_ROOT

    root = tmp_path / "sp"
    dest = root / "01_Clients_Projects" / "Trafilea"
    dest.mkdir(parents=True)
    src = dest / "trafilea-order.pdf"
    src.write_bytes(b"relabel-bytes")
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(cfg_path)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel.json",
        llm_caller=lambda **_: '{"error":"no"}',
    )
    assert report.renamed == 1
    leftover = list(dest.glob("*.pdf"))
    assert leftover
    assert leftover[0].parent == dest
    assert is_organizer_name(leftover[0].name)
    assert not list((root / "01_Clients_Projects").glob("*.pdf"))
    journal.close()


def test_relabel_rule_hit_changes_folder(tmp_path: Path) -> None:
    from harness.config import PACKAGE_ROOT, load_config
    from harness.jobs.relabel import run_relabel
    import yaml

    root = tmp_path / "sp"
    wrong = root / "04_Admin" / "IT"
    wrong.mkdir(parents=True)
    src = wrong / "trafilea-order.pdf"
    src.write_bytes(b"relabel-rehome")
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(cfg_path)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-rehome.json",
        llm_caller=lambda **_: '{"error":"rule hit must not call llm"}',
    )
    target = root / "01_Clients_Projects" / "Trafilea"
    leftover = list(target.glob("*.pdf"))
    assert report.renamed == 1
    assert leftover
    assert leftover[0].parent == target
    assert is_organizer_name(leftover[0].name)
    assert not src.exists()
    journal.close()


def test_relabel_rule_hit_moves_already_named_ledger_file(tmp_path: Path) -> None:
    from harness.config import PACKAGE_ROOT, load_config
    from harness.jobs.relabel import run_relabel
    import yaml

    root = tmp_path / "sp"
    wrong = root / "04_Admin" / "IT"
    wrong.mkdir(parents=True)
    src = wrong / "2026-08-19_PRO_Trafilea Order_v01.pdf"
    src.write_bytes(b"already-named")
    digest = content_hash(src)
    journal_path = tmp_path / "j.sqlite3"
    ledger = DocumentLedger(journal_path)
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title="Trafilea Order",
            prefix="PRO",
            doc_type="PRO",
            doc_date="2026-08-19",
            version=1,
            home="04_Admin",
            current_path=str(src),
            source="relabel_parse",
        )
    )
    ledger.close()
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(journal_path)
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(cfg_path)
    journal = ActionJournal(journal_path)
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-named.json",
        llm_caller=lambda **_: '{"error":"rule hit must not call llm"}',
    )
    target = root / "01_Clients_Projects" / "Trafilea"
    leftover = list(target.glob("*.pdf"))
    assert report.renamed == 1
    assert leftover
    assert leftover[0].parent == target
    assert leftover[0].name == "2026-08-19_PRO_Trafilea Order_v01.pdf"
    assert not src.exists()
    journal.close()


def test_digest_writes_organizer_name_and_ledger(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    src = inbox / "trafilea-order.pdf"
    src.write_bytes(b"pdf-bytes")
    digest = content_hash(src)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    ledger = DocumentLedger(tmp_path / "j.sqlite3")
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
        model="local-driver",
        forbid_host_substrings=["api.openai.com"],
        manifest_path=tmp_path / "manifest.json",
        organizer_names=True,
        ledger=ledger,
        type_by_prefix={"PRO": "Proposal"},
        project_to_brain=False,
    )
    result = sorter.process_file(src, run_id=run_id)
    assert result.status == "moved"
    assert result.dest is not None
    assert is_organizer_name(result.dest.name)
    assert result.dest.name.startswith("20")
    assert "_PRO_" in result.dest.name
    rec = ledger.get(digest)
    assert rec is not None
    assert rec.prefix == "PRO"
    assert rec.doc_type == "Proposal"
    assert rec.home == "01_Clients_Projects"
    journal.close()
    ledger.close()
