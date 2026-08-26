from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from harness.config import PACKAGE_ROOT, load_config, load_correction_rules
from harness.graph.drive_client import FakeGraphDriveClient, ORGANIZER_COLUMNS
from harness.jobs.digest import run_digest
from harness.jobs.relabel import run_relabel
from harness.jobs.stamp import run_stamp
from harness.journal.store import ActionJournal
from harness.naming import readable_title_from_filename
from harness.stamp.embed import minimal_docx_bytes, read_ooxml_core
from harness.stamp.harvest import party_for_document


HAPPY_YARDS_LAW = "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
HAPPY_YARDS_TITLE = "Happy Yards Garden Clean Up Quote"


def _isolated(code: str) -> subprocess.CompletedProcess[str]:
    """Run Python with a clean interpreter so prior test imports cannot hide a cycle."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_harvest_stamp_imports_as_first_harness_stamp_module() -> None:
    """VTA: `from harness.stamp.harvest import HarvestStamp` must work first."""
    proc = _isolated(
        "from harness.stamp.harvest import HarvestStamp; "
        "assert HarvestStamp.__name__ == 'HarvestStamp'"
    )
    assert proc.returncode == 0, proc.stderr


def test_stamp_cli_help_does_not_crash() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "harness.cli.main", "stamp", "--help"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "stamp" in proc.stdout.lower()
    assert "--report" in proc.stdout


def _cfg_for_root(tmp_path: Path, root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p)


def test_readable_title_peels_happy_yards_law_name() -> None:
    assert readable_title_from_filename(HAPPY_YARDS_LAW) == HAPPY_YARDS_TITLE
    assert HAPPY_YARDS_LAW != HAPPY_YARDS_TITLE


def test_digest_and_relabel_stamp_title_columns_and_party(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    src = inbox / HAPPY_YARDS_LAW
    src.write_bytes(b"%PDF-happy-yards")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    report = run_digest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "digest.json",
        graph=graph,
        llm_caller=lambda **_: '{"error":"happy yards rule must not call llm"}',
    )
    assert report.moved >= 1
    dests = list((root / "05_Personal").rglob("*.pdf"))
    assert dests
    dest = dests[0]
    assert dest.name == HAPPY_YARDS_LAW
    fields = graph.item_fields[str(dest)]
    assert fields["Title"] == HAPPY_YARDS_TITLE
    assert fields["Title"] != dest.name
    assert fields["OrganizerParty"] == "Happy Yards"
    assert fields["OrganizerPrefix"] == "INV"
    assert fields["OrganizerHome"] == "05_Personal"
    for col in ORGANIZER_COLUMNS:
        stored = graph.site_columns[col.name]
        assert stored["displayName"] == col.display_name
        assert stored["indexed"] is True
        assert stored["scope"] == "site"
        assert col.name in graph.document_content_type_columns
    journal.close()


def test_relabel_calls_stamp(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "05_Personal" / "Home"
    home.mkdir(parents=True)
    src = home / HAPPY_YARDS_LAW
    src.write_bytes(b"%PDF-relabel-stamp")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel.json",
        graph=graph,
        llm_caller=lambda **_: '{"error":"no"}',
    )
    assert report.scanned >= 1
    assert graph.item_fields
    fields = next(iter(graph.item_fields.values()))
    assert fields["Title"] == HAPPY_YARDS_TITLE
    assert fields["Title"] != HAPPY_YARDS_LAW
    assert fields["OrganizerParty"] == "Happy Yards"
    assert fields["OrganizerPrefix"] == "INV"
    assert fields["OrganizerHome"] == "05_Personal"
    journal.close()


def test_graph_offline_still_writes_embedded_props(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    dest = root / "05_Personal" / "Home"
    dest.mkdir(parents=True)
    src = dest / "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.docx"
    src.write_bytes(minimal_docx_bytes(body="quote"))
    before = src.read_bytes()
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient(online=False)
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-offline.json",
        graph=graph,
    )
    assert report.stamped >= 1
    assert report.columns_written == 0
    assert report.columns_skipped >= 1
    assert graph.item_fields == {}
    assert src.read_bytes() != before
    core = read_ooxml_core(src)
    assert core["title"] == HAPPY_YARDS_TITLE
    assert core["subject"] == HAPPY_YARDS_TITLE
    assert "Happy Yards" in core["keywords"]
    assert "INV" in core["keywords"]
    actions = journal.list_actions(report.run_id)
    assert any(a.payload.get("columns_skipped") for a in actions if a.action_type == "stamp")
    journal.close()


def test_stamp_skips_secrets_and_code_trees(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "04_Admin" / "IT"
    secret_dir = home / ".ssh"
    code_dir = home / "node_modules" / "pkg"
    secret_dir.mkdir(parents=True)
    code_dir.mkdir(parents=True)
    pem = secret_dir / "clawdbot.pem"
    pem.write_text("SECRET-KEY", encoding="utf-8")
    pem_bytes = pem.read_bytes()
    js = code_dir / "index.js"
    js.write_text("module.exports = 1", encoding="utf-8")
    keep = home / HAPPY_YARDS_LAW
    keep.write_bytes(b"%PDF-keep")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-skip.json",
        graph=graph,
    )
    assert pem.read_bytes() == pem_bytes
    assert str(pem) not in graph.item_fields
    assert str(js) not in graph.item_fields
    assert str(keep) in graph.item_fields
    assert graph.item_fields[str(keep)]["Title"] == HAPPY_YARDS_TITLE
    assert report.stamped >= 1
    journal.close()


def test_stamp_job_is_rename_free_and_honors_limit(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "02_Business_Ops"
    home.mkdir(parents=True)
    first = home / "2026-08-18_GEN_Alpha Memo_v01.pdf"
    second = home / "2026-08-18_GEN_Beta Memo_v01.pdf"
    first.write_bytes(b"alpha")
    second.write_bytes(b"beta")
    capture = root / "00_Inbox" / "_from_mail"
    capture.mkdir(parents=True)
    leftover = capture / "2026-08-18_GEN_Should Skip Capture_v01.pdf"
    leftover.write_bytes(b"mail")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-limit.json",
        graph=graph,
        limit=1,
    )
    assert first.exists() and first.name == "2026-08-18_GEN_Alpha Memo_v01.pdf"
    assert second.exists() and second.name == "2026-08-18_GEN_Beta Memo_v01.pdf"
    assert leftover.exists()
    assert report.scanned == 1
    assert str(leftover) not in graph.item_fields
    titled = {fields["Title"] for fields in graph.item_fields.values()}
    assert titled == {"Alpha Memo"} or titled == {"Beta Memo"}
    journal.close()


def test_party_from_rule_else_conservative_empty() -> None:
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    assert (
        party_for_document(
            filename=HAPPY_YARDS_LAW,
            title=HAPPY_YARDS_TITLE,
            rules=rules,
        )
        == "Happy Yards"
    )
    assert (
        party_for_document(
            filename="2026-08-18_GEN_Untitled Notes_v01.pdf",
            title="Untitled Notes",
            rules=[],
        )
        == ""
    )


def test_stamp_folder_walk_does_not_fold_leftover_trees(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "02_Business_Ops"
    leftover = root / "artifacts"
    home.mkdir(parents=True)
    leftover.mkdir(parents=True)
    keep = home / "2026-08-18_GEN_Alpha Memo_v01.pdf"
    skip = leftover / "2026-08-18_GEN_Should Skip Leftover_v01.pdf"
    keep.write_bytes(b"alpha")
    skip.write_bytes(b"nope")
    cfg = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-leftover.json",
        graph=graph,
    )
    assert keep.exists() and keep.name == "2026-08-18_GEN_Alpha Memo_v01.pdf"
    assert skip.exists() and skip.name == "2026-08-18_GEN_Should Skip Leftover_v01.pdf"
    assert str(keep) in graph.item_fields
    assert str(skip) not in graph.item_fields
    assert all("artifacts" not in Path(p).parts for p in graph.item_fields)
    assert report.stamped >= 1
    journal.close()


def test_docs_name_locked_column_contract_and_copilot_constraints() -> None:
    adr = (PACKAGE_ROOT / "docs" / "adr" / "0025-sharepoint-columns-are-a-projection.md").read_text(
        encoding="utf-8"
    )
    ops = (PACKAGE_ROOT / "docs" / "ops.md").read_text(encoding="utf-8")
    for text in (adr, ops):
        assert "OrganizerParty" in text
        assert "OrganizerPrefix" in text
        assert "OrganizerHome" in text
        assert "semantic-index-for-copilot" in text
        assert "Allow this site to appear in search results" in text
        assert "autofill" in text.lower()
    assert "ows_OrganizerParty" in ops
    assert "RefinableString00" in ops
    assert "manage-search-schema" in ops
    assert "Do not archive" in ops
