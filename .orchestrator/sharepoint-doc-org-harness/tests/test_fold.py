from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from harness.actions.fold import (
    FoldApplyBlocked,
    constrain_fold_destination,
    guard_apply,
    load_leftover_trees_config,
    taxonomy_homes,
)
from harness.classify.router import UNSORTED_FOLDER, classify_with_order
from harness.cli.main import main
from harness.config import PACKAGE_ROOT, HarnessConfig, load_config, load_correction_rules
from harness.jobs.fold import NEVER_ARCHIVE, NEVER_HIDE, run_fold
from harness.journal.store import ActionJournal

TAXONOMY = [
    "00_Inbox",
    "01_Clients_Projects",
    "02_Business_Ops",
    "03_Marketing_Creative",
    "04_Admin",
    "05_Personal",
    "06_Reference",
]


def _write_cfg(tmp_path: Path, root: Path) -> tuple[HarnessConfig, Path]:
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(cfg_path), cfg_path


def _build_fixture(root: Path) -> dict[str, Path]:
    for home in TAXONOMY:
        (root / home).mkdir(parents=True)

    files: dict[str, Path] = {}

    hy_tree = root / "Documents" / "Open Orders" / "Happy Valley" / "open-order.txt"
    hy_tree.parent.mkdir(parents=True)
    hy_tree.write_text("leftover Happy Valley pile, not a filed expense", encoding="utf-8")
    files["happy_valley"] = hy_tree

    hy_inv = root / "Documents" / "Happy Yards invoice.pdf"
    hy_inv.write_bytes(b"%PDF-happy-yards")
    files["happy_yards"] = hy_inv

    secret = root / "Documents" / ".aws" / "credentials"
    secret.parent.mkdir(parents=True)
    secret.write_text("AKIAEXAMPLE", encoding="utf-8")
    files["secret"] = secret

    for name in (
        "Daily Reports",
        "Command Center",
        "cursor-inbox",
        "Lattice-Peptides",
        "Projects",
    ):
        (root / name).mkdir()
    (root / "Daily Reports" / "day.txt").write_text("report", encoding="utf-8")
    (root / "Command Center" / "note.txt").write_text("ops", encoding="utf-8")
    (root / "cursor-inbox" / "drop.md").write_text("inbox", encoding="utf-8")
    (root / "Lattice-Peptides" / "peptide.txt").write_text("lab", encoding="utf-8")
    (root / "Projects" / "old-project.txt").write_text("proj", encoding="utf-8")

    git_file = root / "Projects" / "agentic-swarm" / "src" / "x.py"
    git_file.parent.mkdir(parents=True)
    git_file.write_text("print('no')\n", encoding="utf-8")
    (root / "Projects" / "agentic-swarm" / ".git").mkdir()
    (root / "Projects" / "agentic-swarm" / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    files["code"] = git_file

    petra = root / "01_Clients_Projects" / "Petra" / "petra-note.txt"
    petra.parent.mkdir(parents=True)
    petra.write_text("petra leftover", encoding="utf-8")
    files["petra"] = petra

    admin_docs = root / "04_Admin" / "Documents"
    admin_docs.mkdir(parents=True)
    files["admin_a"] = admin_docs / "old-memo.txt"
    files["admin_b"] = admin_docs / "second-memo.txt"
    files["admin_c"] = admin_docs / "third-memo.txt"
    for key in ("admin_a", "admin_b", "admin_c"):
        files[key].write_text("admin swamp", encoding="utf-8")

    gen_docs = root / "04_Admin" / "General_Docs" / "dump.txt"
    gen_docs.parent.mkdir(parents=True)
    gen_docs.write_text("general dump", encoding="utf-8")
    files["general"] = gen_docs

    keep = root / "04_Admin" / "Meeting_Notes" / "standup.txt"
    keep.parent.mkdir(parents=True)
    keep.write_text("keep me in taxonomy", encoding="utf-8")
    files["keep"] = keep

    misc = root / "05_Personal" / "Misc" / "receipt-invoice.txt"
    misc.parent.mkdir(parents=True)
    misc.write_text("Invoice 123", encoding="utf-8")
    files["misc_invoice"] = misc

    expenses = root / "05_Personal" / "Expenses"
    expenses.mkdir(parents=True)

    return files


def test_leftover_config_does_not_list_taxonomy_homes() -> None:
    spec = load_leftover_trees_config(PACKAGE_ROOT / "config" / "leftover_trees.yaml")
    homes = set(taxonomy_homes())
    assert not (homes & set(spec["nested"]))
    assert not (homes & set(spec["known_roots"]))
    assert "04_Admin/Documents" in spec["nested"]
    assert "05_Personal/Misc" in spec["nested"]
    assert "Documents" in spec["known_roots"]


def test_constrain_fold_never_archives_or_stays_in_swamp() -> None:
    assert constrain_fold_destination("_Archive/2024", "Documents") == UNSORTED_FOLDER
    assert constrain_fold_destination("04_Admin/Documents", "04_Admin/Documents") == UNSORTED_FOLDER
    assert (
        constrain_fold_destination(
            "02_Business_Ops/Finance/Invoices_Receivable",
            "04_Admin/Documents",
        )
        == "02_Business_Ops/Finance/Invoices_Receivable"
    )


def test_classify_order_rule_then_heuristic_then_llm() -> None:
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    calls: list[str] = []

    def llm(**kw: object) -> str:
        calls.append(str(kw.get("filename")))
        return (
            '{"prefix":"REF","target_folder":"06_Reference",'
            '"description":"Dump","confidence":0.7}'
        )

    rule = classify_with_order(
        path=Path("Happy Yards invoice.pdf"),
        text="ignored",
        rules=rules,
        llm_caller=llm,
    )
    assert rule.source == "correction_rule"
    assert "Expenses" in rule.target_folder

    heur = classify_with_order(
        path=Path("receipt-invoice.txt"),
        text="Invoice 123",
        rules=rules,
        llm_caller=llm,
    )
    assert heur.source == "heuristic"
    assert heur.prefix == "INV"

    gen = classify_with_order(
        path=Path("open-order.txt"),
        text="leftover pile",
        rules=rules,
        llm_caller=llm,
    )
    assert gen.source == "llm"
    assert gen.target_folder == "06_Reference"
    assert calls == ["open-order.txt"]


def test_fold_dry_run_report_format_and_does_not_move(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _write_cfg(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report_path = tmp_path / "fold.json"
    try:
        report = run_fold(cfg=cfg, journal=journal, report_path=report_path)
    finally:
        journal.close()

    assert report.apply is False
    assert report.dry_run is True
    assert report.moved == 0
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["apply"] is False
    assert payload["dry_run"] is True
    assert payload["taxonomy_homes"] == sorted(TAXONOMY)
    assert "leftover_vs_taxonomy" in payload
    assert "00_Inbox" in payload["leftover_vs_taxonomy"]["taxonomy"]
    assert "Documents" in payload["leftover_vs_taxonomy"]["leftover_roots"]
    assert "04_Admin/Documents" in payload["leftover_vs_taxonomy"]["nested_leftovers"]
    assert NEVER_HIDE in payload["notes"]
    assert NEVER_ARCHIVE in payload["notes"]
    assert "apply=false; pass --apply to execute moves" in payload["notes"]

    rels = {row["rel"]: row for row in payload["leftover_trees"]}
    assert rels["Documents"]["file_count"] >= 2
    assert rels["04_Admin/Documents"]["file_count"] == 3
    assert rels["05_Personal/Misc"]["file_count"] == 1
    assert rels["04_Admin/Documents"]["file_count"] > rels["05_Personal/Misc"]["file_count"]
    assert report.skipped_secret >= 1
    assert report.skipped_code >= 1

    hy_plan = next(item for item in payload["files"] if "Happy Yards invoice.pdf" in item["src"])
    assert hy_plan["status"] == "plan"
    assert hy_plan["source"] == "correction_rule"
    assert "05_Personal" in hy_plan["dest"] and "Expenses" in hy_plan["dest"]

    misc_plan = next(item for item in payload["files"] if item["src"].endswith("receipt-invoice.txt"))
    assert misc_plan["source"] == "heuristic"
    assert "Invoices_Receivable" in misc_plan["dest"]

    assert files["happy_yards"].exists()
    assert files["happy_valley"].exists()
    assert files["keep"].exists()
    assert files["secret"].exists()
    assert files["code"].exists()
    assert not (root / "_Archive").exists()
    for home in TAXONOMY:
        assert (root / home).is_dir()
    assert not (root / "05_Personal" / "Expenses" / "Happy Yards invoice.pdf").exists()


def test_fold_apply_moves_and_leaves_taxonomy_homes(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _write_cfg(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        dry = run_fold(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "fold-dry.json",
            apply=False,
        )
        assert dry.moved == 0
        assert files["happy_yards"].exists()

        live = run_fold(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "fold-apply.json",
            apply=True,
        )
    finally:
        journal.close()

    assert live.apply is True
    assert live.dry_run is False
    assert live.moved >= 1
    assert not files["happy_yards"].exists()
    assert (root / "05_Personal" / "Expenses" / "Happy Yards invoice.pdf").exists()
    assert not files["misc_invoice"].exists()
    assert (
        root / "02_Business_Ops" / "Finance" / "Invoices_Receivable" / "receipt-invoice.txt"
    ).exists()
    assert files["keep"].exists()
    assert files["secret"].exists()
    assert files["code"].exists()
    assert not (root / "_Archive").exists()
    for home in TAXONOMY:
        assert (root / home).is_dir()
    assert root.exists()


def test_fold_cli_defaults_to_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    _, cfg_path = _write_cfg(tmp_path, root)
    report_path = tmp_path / "cli-fold.json"
    rc = main(
        [
            "--config",
            str(cfg_path),
            "fold",
            "--report",
            str(report_path),
            "--journal",
            str(tmp_path / "cli.sqlite3"),
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["apply"] is False
    assert payload["moved"] == 0
    assert files["happy_yards"].exists()


def test_fold_cli_apply_is_opt_in(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    _, cfg_path = _write_cfg(tmp_path, root)
    rc = main(
        [
            "--config",
            str(cfg_path),
            "fold",
            "--report",
            str(tmp_path / "cli-apply.json"),
            "--journal",
            str(tmp_path / "cli-apply.sqlite3"),
            "--apply",
        ]
    )
    assert rc == 0
    payload = json.loads((tmp_path / "cli-apply.json").read_text(encoding="utf-8"))
    assert payload["apply"] is True
    assert payload["moved"] >= 1
    assert not files["happy_yards"].exists()
    assert (root / "05_Personal" / "Expenses" / "Happy Yards invoice.pdf").exists()


def test_fold_apply_blocked_on_cloud_against_live_root(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("live-root apply guard is for Cloud/Linux VMs")
    live = tmp_path / "OneDrive - Petra Hygienic Systems Int Ltd" / "Vince Personal - Documents"
    live.mkdir(parents=True)
    (live / "Documents").mkdir()
    (live / "Documents" / "trap.txt").write_text("do not fold", encoding="utf-8")
    cfg, _ = _write_cfg(tmp_path, live)
    journal = ActionJournal(tmp_path / "blocked.sqlite3")
    try:
        with pytest.raises(FoldApplyBlocked, match="Cloud VM"):
            run_fold(
                cfg=cfg,
                journal=journal,
                report_path=tmp_path / "blocked.json",
                apply=True,
            )
    finally:
        journal.close()
    assert (live / "Documents" / "trap.txt").exists()


def test_fold_cli_apply_blocked_against_default_live_root(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("live-root apply guard is for Cloud/Linux VMs")
    rc = main(
        [
            "fold",
            "--report",
            str(tmp_path / "live.json"),
            "--journal",
            str(tmp_path / "live.sqlite3"),
            "--apply",
        ]
    )
    assert rc == 2
    assert not (tmp_path / "live.json").exists()


def test_fold_never_hides_vince_personal() -> None:
    fold_job = (PACKAGE_ROOT / "harness" / "jobs" / "fold.py").read_text(encoding="utf-8")
    fold_actions = (PACKAGE_ROOT / "harness" / "actions" / "fold.py").read_text(encoding="utf-8")
    cli = (PACKAGE_ROOT / "harness" / "cli" / "main.py").read_text(encoding="utf-8")
    blob = fold_job + fold_actions + cli
    assert "hide-petra" not in blob.lower()
    assert NEVER_HIDE in fold_job
    assert "Vince Personal" in (
        PACKAGE_ROOT / "scripts" / "hide-petra-sources.ps1"
    ).read_text(encoding="utf-8")


def test_guard_apply_is_noop_without_flag(tmp_path: Path) -> None:
    live = tmp_path / "OneDrive - Petra Hygienic Systems Int Ltd" / "Vince Personal - Documents"
    guard_apply(live, apply=False)
