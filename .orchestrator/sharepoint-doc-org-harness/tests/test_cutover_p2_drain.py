from __future__ import annotations

from pathlib import Path

from harness.actions.drain import load_drain_map, plan_unique_files, resolve_home
from harness.config import PACKAGE_ROOT


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
    assert resolve_home("OLD LAPTOP FILES/x.bin", mapping) == "00_Inbox"


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
