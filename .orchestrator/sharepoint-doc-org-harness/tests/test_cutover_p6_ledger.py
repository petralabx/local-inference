from __future__ import annotations

from pathlib import Path

from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.ledger.brain import project_document
from harness.ledger.documents import DocumentLedger, DocumentRecord
from harness.actions.inbox import InboxSorter
from harness.graph.drive_client import FakeGraphDriveClient
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


HAPPY_YARDS_STACKED = (
    "2026-08-18_INV_2026-08-18_01_CLIENTS_PROJECTS_"
    "Happy Yards Garden Clean Up Quote_v01_v01.pdf"
)
HAPPY_YARDS_LAW = "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"


def _relabel_cfg(tmp_path: Path, root: Path):
    from harness.config import PACKAGE_ROOT, load_config
    import yaml

    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(cfg_path)


def test_relabel_peels_stacked_happy_yards_already_in_ledger(tmp_path: Path) -> None:
    from harness.jobs.relabel import run_relabel

    root = tmp_path / "sp"
    home = root / "01_Clients_Projects" / "Happy Yards"
    home.mkdir(parents=True)
    src = home / HAPPY_YARDS_STACKED
    src.write_bytes(b"happy-yards-stacked")
    digest = content_hash(src)
    journal_path = tmp_path / "j.sqlite3"
    ledger = DocumentLedger(journal_path)
    ledger.upsert(
        DocumentRecord(
            sha256=digest,
            title="Happy Yards Garden Clean Up Quote",
            prefix="INV",
            doc_type="Invoice",
            doc_date="2026-08-18",
            version=1,
            home="01_Clients_Projects",
            current_path=str(src),
            source="relabel_parse",
        )
    )
    ledger.close()
    cfg = _relabel_cfg(tmp_path, root)
    journal = ActionJournal(journal_path)
    llm_calls = {"n": 0}

    def _boom(**_: object) -> str:
        llm_calls["n"] += 1
        raise AssertionError("stacked leftover must peel without a model")

    graph = FakeGraphDriveClient()
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-happy-yards.json",
        llm_caller=_boom,
        graph=graph,
    )
    law = list((root / "05_Personal" / "Expenses").glob("*.pdf"))
    assert report.peeled == 1
    assert report.renamed == 1
    assert llm_calls["n"] == 0
    assert law
    assert law[0].name == HAPPY_YARDS_LAW
    assert is_organizer_name(law[0].name)
    assert not src.exists()
    rec = DocumentLedger(journal_path).get(digest)
    assert rec is not None
    assert rec.title == "Happy Yards Garden Clean Up Quote"
    assert rec.prefix == "INV"
    assert rec.home == "05_Personal"
    fields = graph.item_fields[str(law[0])]
    assert fields["Title"] == "Happy Yards Garden Clean Up Quote"
    assert fields["OrganizerPrefix"] == "INV"
    journal.close()


def test_relabel_peels_folder_and_visual_version_leftovers(tmp_path: Path) -> None:
    from harness.jobs.relabel import run_relabel

    root = tmp_path / "sp"
    ops = root / "02_Business_Ops" / "Finance"
    personal = root / "05_Personal" / "Home"
    ops.mkdir(parents=True)
    personal.mkdir(parents=True)
    leftover_ops = ops / "2026-08-18_BUSINESS_OPS_Vendor Invoice_v01_v01.pdf"
    leftover_personal = personal / "2026-08-18_PERSONAL_Vacation Photos_v01.jpg"
    keep_q4 = ops / "2026-08-18_INV_Q4_Report_v01.pdf"
    keep_sop = ops / "2026-08-18_GEN_SOP_Template_v01.docx"
    leftover_ops.write_bytes(b"ops-stacked")
    leftover_personal.write_bytes(b"personal-stacked")
    keep_q4.write_bytes(b"keep-acronym-title")
    keep_sop.write_bytes(b"keep-known-prefix-title")
    cfg = _relabel_cfg(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-leftovers.json",
        llm_caller=lambda **_: (_ for _ in ()).throw(
            AssertionError("folder leftovers must peel without a model")
        ),
    )
    assert report.peeled == 2
    assert (ops / "2026-08-18_GEN_Vendor Invoice_v01.pdf").exists()
    assert (personal / "2026-08-18_GEN_Vacation Photos_v01.jpg").exists()
    assert keep_q4.exists()
    assert keep_q4.name == "2026-08-18_INV_Q4_Report_v01.pdf"
    assert keep_sop.exists()
    assert keep_sop.name == "2026-08-18_GEN_SOP_Template_v01.docx"
    assert not leftover_ops.exists()
    assert not leftover_personal.exists()
    journal.close()


def test_relabel_proof_limit_prefers_stacked_names(tmp_path: Path) -> None:
    from harness.jobs.relabel import run_relabel

    root = tmp_path / "sp"
    home = root / "01_Clients_Projects"
    home.mkdir(parents=True)
    already = home / "2026-08-18_GEN_Already Law Memo_v01.pdf"
    already.write_bytes(b"already-law")
    stacked = home / HAPPY_YARDS_STACKED
    stacked.write_bytes(b"needs-peel")
    leftover_tree = root / "artifacts" / "Projects"
    leftover_tree.mkdir(parents=True)
    parked = leftover_tree / HAPPY_YARDS_STACKED
    parked.write_bytes(b"do-not-fold")
    secret_dir = home / ".ssh"
    secret_dir.mkdir()
    secret = secret_dir / "stacked.pem"
    secret.write_bytes(b"SECRET-KEY")
    code_dir = home / "node_modules" / "pkg"
    code_dir.mkdir(parents=True)
    coded = code_dir / HAPPY_YARDS_STACKED
    coded.write_bytes(b"code-tree")
    cfg = _relabel_cfg(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-proof.json",
        llm_caller=lambda **_: '{"error":"peel must not call llm"}',
        limit=1,
    )
    assert report.scanned == 1
    assert report.peeled == 1
    assert "limit=1" in report.notes
    assert "peel_first=1" in report.notes
    assert already.exists()
    assert already.name == "2026-08-18_GEN_Already Law Memo_v01.pdf"
    assert parked.exists()
    assert parked.read_bytes() == b"do-not-fold"
    assert secret.exists()
    assert coded.exists()
    law = list((root / "05_Personal" / "Expenses").glob("*.pdf"))
    assert law
    assert law[0].name == HAPPY_YARDS_LAW
    journal.close()
