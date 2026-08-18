from __future__ import annotations

from pathlib import Path

from harness.actions.drain import (
    dest_relative,
    is_secret_file,
    load_drain_map,
    plan_unique_files,
    resolve_home,
)
from harness.config import PACKAGE_ROOT, load_config
from harness.jobs.drain import run_drain
from harness.journal.store import ActionJournal


def test_cutover_petra_map_adr_0016() -> None:
    mapping = load_drain_map(PACKAGE_ROOT / "config" / "drain_map.yaml")
    assert resolve_home("01_Projects/foo.pdf", mapping) == "01_Clients_Projects"
    assert resolve_home("02_Customers/x.docx", mapping) == "01_Clients_Projects"
    assert resolve_home("03_Finance/inv.pdf", mapping) == "02_Business_Ops"
    assert resolve_home("05_HR/offer.pdf", mapping) == "04_Admin"
    assert resolve_home("06_Marketing/ad.png", mapping) == "03_Marketing_Creative"
    assert resolve_home("07_Admin/note.txt", mapping) == "04_Admin"
    assert resolve_home("08_Personal/tax.pdf", mapping) == "05_Personal"
    assert resolve_home("CursorInbox/a.md", mapping) == "00_Inbox"
    assert resolve_home("Microsoft Teams Chat Files/a.png", mapping) == "00_Inbox"
    assert resolve_home("OLD LAPTOP FILES/x.bin", mapping) == "00_Inbox"
    assert resolve_home("09_Archive/2024/scan.pdf", mapping) == "00_Inbox"
    assert resolve_home("Notebooks/note.one", mapping) == "00_Inbox"


def test_cutover_unique_hash_skip(tmp_path: Path) -> None:
    src = tmp_path / "petra"
    src.mkdir()
    a = src / "01_Projects" / "one.pdf"
    b = src / "Vince Backup" / "copy.pdf"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"same-bytes")
    b.write_bytes(b"same-bytes")
    other = src / "01_Projects" / "two.pdf"
    other.write_bytes(b"unique-bytes")
    mapping = load_drain_map(PACKAGE_ROOT / "config" / "drain_map.yaml")
    plan = plan_unique_files([a, b, other], source_root=src, mapping=mapping, known_hashes=set())
    statuses = {p.src.name: p.status for p in plan}
    assert statuses["one.pdf"] == "plan"
    assert statuses["copy.pdf"] == "skip_duplicate"
    assert statuses["two.pdf"] == "plan"
    assert plan[0].dest_home == "01_Clients_Projects"


def test_cutover_dest_keeps_remainder_and_skips_secrets() -> None:
    assert dest_relative("01_Projects/A1/one.pdf", "01_Clients_Projects") == Path(
        "01_Clients_Projects/A1/one.pdf"
    )
    assert dest_relative("00_INBOX/note.txt", "00_Inbox") == Path("00_Inbox/note.txt")
    assert is_secret_file(Path("07_Admin/.aws/credentials"))
    assert is_secret_file(Path("vault/id_ed25519"))
    assert not is_secret_file(Path("01_Projects/A1/one.pdf"))


def test_cutover_drain_moves_unique_and_skips_hash_copy(tmp_path: Path) -> None:
    petra = tmp_path / "petra"
    dest = tmp_path / "Vince Personal - Documents"
    src = petra / "00_INBOX" / "note.txt"
    dup = petra / "Vince Backup" / "note-copy.txt"
    src.parent.mkdir(parents=True)
    dup.parent.mkdir(parents=True)
    dest.mkdir()
    src.write_text("unique-inbox", encoding="utf-8")
    dup.write_text("unique-inbox", encoding="utf-8")
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    cfg = cfg.model_copy(update={"sharepoint_sync_root": str(dest)})
    journal = ActionJournal(tmp_path / "journal.sqlite3")
    try:
        report = run_drain(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "drain.json",
            source_root=petra,
            only=["00_INBOX", "Vince Backup"],
        )
    finally:
        journal.close()
    assert report.moved == 1
    assert report.skipped_duplicate == 1
    assert (dest / "00_Inbox" / "note.txt").read_text(encoding="utf-8") == "unique-inbox"
    assert dup.exists()
    assert not src.exists()


def test_cutover_collects_petra_root_files(tmp_path: Path) -> None:
    from harness.actions.drain import collect_source_files

    src = tmp_path / "petra"
    src.mkdir()
    (src / "09_Archive").mkdir()
    (src / "09_Archive" / "old.pdf").write_bytes(b"arch")
    (src / "Book.xlsx").write_bytes(b"root-unique")
    (src / "desktop.ini").write_text("[.ShellClassInfo]", encoding="utf-8")
    mapping = load_drain_map(PACKAGE_ROOT / "config" / "drain_map.yaml")
    files = collect_source_files(src, mapping, only=["09_Archive", "_root"])
    names = {p.name for p in files}
    assert names == {"old.pdf", "Book.xlsx"}


def test_cutover_legacy_roots_map_skips_canonical_homes() -> None:
    mapping = load_drain_map(PACKAGE_ROOT / "config" / "legacy_roots.yaml")
    canon = {
        "00_Inbox",
        "01_Clients_Projects",
        "02_Business_Ops",
        "03_Marketing_Creative",
        "04_Admin",
        "05_Personal",
        "06_Reference",
    }
    assert not (canon & set(mapping))
    assert mapping["cursor-inbox"] == "00_Inbox"
    assert mapping["Happy Yards"] == "01_Clients_Projects"
    assert mapping["artifacts"].startswith("06_Reference/legacy-2026/")
