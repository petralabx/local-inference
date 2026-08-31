"""Live 2026-08-31 VTA learnings: unstall, --only, stamp 404, home lock."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from harness.cli.main import main
from harness.config import PACKAGE_ROOT, load_config
from harness.graph.drive_client import FakeGraphDriveClient, GraphNotFoundError
from harness.jobs.harvest import run_harvest
from harness.jobs.home_lock import HomeLockSet, lock_dir_for_journal
from harness.jobs.pass_status import decide_pass
from harness.jobs.relabel import homes_for_relabel, iter_relabel_files, run_relabel
from harness.jobs.stamp import run_stamp
from harness.journal.store import ActionJournal
from harness.naming import held_reason_for_name, looks_like_bad_organizer_date
HAPPY_YARDS_LAW = "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
INVALID_MONTH_NAME = "2022-20-03_PRO_Related_Items_Import_v01.xls"


def _cfg_for_root(tmp_path: Path, root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p), p


def test_completed_pass_is_not_restarted_when_pid_dead() -> None:
    report = {
        "run_id": "201236823ca6417bb59e8a6c8e668a7e",
        "finished_at": "2026-08-31T20:02:00+00:00",
        "homes": ["05_Personal", "01_Clients_Projects", "00_Inbox"],
        "completed_homes": ["05_Personal", "01_Clients_Projects", "00_Inbox"],
        "held": 9429,
        "errors": 0,
    }
    decision = decide_pass(report=report, pid_alive=False)
    assert decision.action == "done"
    assert decision.homes == []
    assert decision.completed_homes == [
        "05_Personal",
        "01_Clients_Projects",
        "00_Inbox",
    ]


def test_pid_dead_unfinished_report_restarts_remaining_homes() -> None:
    report = {
        "finished_at": "",
        "homes": ["05_Personal", "01_Clients_Projects", "00_Inbox"],
        "completed_homes": ["05_Personal"],
    }
    decision = decide_pass(report=report, pid_alive=False)
    assert decision.action == "restart"
    assert decision.homes == ["01_Clients_Projects", "00_Inbox"]


def test_completed_pass_advances_to_next_incomplete_homes() -> None:
    report = {
        "finished_at": "2026-08-31T20:02:00+00:00",
        "homes": ["05_Personal", "01_Clients_Projects", "00_Inbox"],
        "completed_homes": ["05_Personal", "01_Clients_Projects", "00_Inbox"],
    }
    decision = decide_pass(
        report=report,
        pid_alive=False,
        next_homes=["02_Business_Ops", "03_Marketing_Creative", "04_Admin", "06_Reference"],
    )
    assert decision.action == "advance"
    assert decision.homes == [
        "02_Business_Ops",
        "03_Marketing_Creative",
        "04_Admin",
        "06_Reference",
    ]


def test_relabel_only_filters_homes(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    keep_dir = root / "02_Business_Ops" / "Finance"
    skip_dir = root / "05_Personal" / "Expenses"
    keep_dir.mkdir(parents=True)
    skip_dir.mkdir(parents=True)
    keep = keep_dir / "keep.pdf"
    skip = skip_dir / "skip-me.pdf"
    keep.write_bytes(b"keep")
    skip.write_bytes(b"skip")
    assert homes_for_relabel(["02_Business_Ops"]) == ["02_Business_Ops"]
    files = iter_relabel_files(root, [], only=["02_Business_Ops"])
    assert keep in files
    assert skip not in files


def test_relabel_cli_help_lists_only() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "harness.cli.main", "relabel", "--help"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--only" in proc.stdout


def test_relabel_cli_passes_only(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    (root / "02_Business_Ops").mkdir(parents=True)
    (root / "05_Personal").mkdir(parents=True)
    _, cfg_path = _cfg_for_root(tmp_path, root)
    report_path = tmp_path / "relabel-only.json"
    rc = main(
        [
            "--config",
            str(cfg_path),
            "relabel",
            "--report",
            str(report_path),
            "--only",
            "02_Business_Ops",
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["homes"] == ["02_Business_Ops"]
    assert "05_Personal" not in payload["homes"]


def test_stamp_404_is_not_counted_success(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "05_Personal"
    home.mkdir(parents=True)
    src = home / HAPPY_YARDS_LAW
    src.write_bytes(b"%PDF-404")
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient(missing_paths={str(src)})
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-404-count.json",
        graph=graph,
    )
    assert report.stamped == 0
    assert report.columns_written == 0
    assert report.skipped >= 1
    blob = " ".join(report.skip_reasons + report.notes)
    assert "404" in blob
    actions = journal.list_actions(report.run_id)
    stamp_actions = [a for a in actions if a.action_type == "stamp"]
    assert stamp_actions
    assert all(not a.payload.get("columns_written") for a in stamp_actions)
    assert any(
        str(a.payload.get("skipped") or a.payload.get("columns_skip_reason") or "").startswith(
            "404"
        )
        or "404" in str(a.payload.get("skipped") or a.payload.get("columns_skip_reason") or "")
        for a in stamp_actions
    )
    journal.close()


def test_stamp_backfill_retries_by_item_id_after_rename(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "05_Personal"
    home.mkdir(parents=True)
    dest = home / HAPPY_YARDS_LAW
    dest.write_bytes(b"%PDF-backfill")
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient(
        missing_paths={str(dest)},
        item_ids={str(dest): "list-item-77"},
    )
    run_id = journal.start_run(note="stamp-404")
    journal.record(
        run_id,
        "stamp",
        {
            "path": str(dest),
            "columns_written": False,
            "columns_skipped": True,
            "columns_skip_reason": "404:pre-rename path",
            "item_id": "list-item-77",
            "skipped": "graph_404",
        },
    )
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-backfill.json",
        graph=graph,
        backfill=True,
    )
    assert report.stamped >= 1
    assert report.columns_written >= 1
    assert graph.fields_by_id["list-item-77"]["Title"] == "Happy Yards Garden Clean Up Quote"
    journal.close()


def test_harvest_stamp_404_is_not_counted_success(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "05_Personal" / "Expenses"
    home.mkdir(parents=True)
    src = home / HAPPY_YARDS_LAW
    src.write_bytes(b"%PDF-local-only")
    rel = "05_Personal/Expenses/" + src.name
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient(missing_paths={str(src)})

    def boom(item_path: str, fields: dict, *, item_id=None):
        raise GraphNotFoundError(f"404 {item_path}")

    graph.patch_list_item_fields = boom  # type: ignore[method-assign]
    report = run_harvest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "harvest-404.json",
        graph=graph,
        apply=True,
        local_only=[{"path": rel, "size": src.stat().st_size}],
    )
    assert report.uploaded == 1
    assert report.stamped == 0
    assert report.columns_written == 0
    journal.close()


def test_harvest_refuses_home_with_live_relabel_lock(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "05_Personal" / "Expenses"
    home.mkdir(parents=True)
    src = home / HAPPY_YARDS_LAW
    src.write_bytes(b"%PDF-locked")
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    locks = HomeLockSet(
        lock_dir_for_journal(Path(cfg.journal_path)),
        ["05_Personal"],
        job="relabel",
        pid=os_getpid(),
    )
    locks.acquire()
    try:
        report = run_harvest(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "harvest-locked.json",
            graph=FakeGraphDriveClient(),
            apply=False,
            only=["05_Personal"],
            local_only=[{"path": "05_Personal/Expenses/" + src.name, "size": 4}],
        )
        assert report.planned == 0
        assert report.uploaded == 0
        assert any("relabel_lock" in n for n in report.notes)
    finally:
        locks.release()
        journal.close()


def test_relabel_held_reason_histogram(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    personal = root / "05_Personal" / "Expenses"
    clients = root / "01_Clients_Projects" / "ClawdBot" / "Telegram Desktop" / "media"
    personal.mkdir(parents=True)
    clients.mkdir(parents=True)
    (personal / INVALID_MONTH_NAME).write_bytes(b"bad-date")
    (personal / "untitled-scan.pdf").write_bytes(b"no-entity")
    (personal / ".git-credentials").write_text("https://x:y@github.com\n", encoding="utf-8")
    (personal / ".gitconfig").write_text("[user]\n", encoding="utf-8")
    (personal / "2026-08-18_INV_Happy Yards Invoice_v01.pdf").write_bytes(b"entity-topic")
    (clients / "photo.jpg").write_bytes(b"telegram-cache")
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    report = run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-hist.json",
        only=["05_Personal", "01_Clients_Projects"],
        llm_caller=lambda **_: (
            '{"prefix":"GEN","target_folder":"00_Inbox/_Unsorted_Imports",'
            '"entity":"","topic":"Untitled","confidence":0.2}'
        ),
    )
    hist = report.held_reasons
    assert hist.get("skip_telegram", 0) >= 1
    assert hist.get("skip_bad_date", 0) >= 1
    assert hist.get("skip_secret", 0) >= 2
    assert hist.get("unknown_entity", 0) >= 1 or hist.get("weak_title", 0) >= 1
    assert hist.get("already_entity_topic_llm_empty", 0) == 0
    assert looks_like_bad_organizer_date(INVALID_MONTH_NAME)
    hold_rows = [a for a in journal.list_actions(report.run_id) if a.action_type == "hold"]
    assert hold_rows
    assert all(a.payload.get("reason") for a in hold_rows)
    still = personal / "2026-08-18_INV_Happy Yards Invoice_v01.pdf"
    assert still.is_file()
    journal.close()


def test_held_reason_buckets_from_filename_shape() -> None:
    assert (
        held_reason_for_name("2026-08-18_INV_Happy Yards Invoice_v01.pdf")
        == "already_entity_topic_llm_empty"
    )
    assert held_reason_for_name("2026-08-18_GEN_Invoice_v01.pdf") == "weak_title"
    assert held_reason_for_name("Copy of Invoice.pdf") == "weak_title"
    assert held_reason_for_name("random-bytes.bin") == "unknown_entity"


def os_getpid() -> int:
    import os

    return os.getpid()


def test_pr52_skip_still_on_main() -> None:
    """Do not re-implement PR #52. This only asserts the skip helpers remain."""
    from harness.jobs.relabel import JUNK_CACHE_DIR_NAMES
    from harness.naming import is_organizer_name, peel_rebuild_organizer_name

    assert "telegram desktop" in JUNK_CACHE_DIR_NAMES
    assert "clawdbot" in JUNK_CACHE_DIR_NAMES
    assert peel_rebuild_organizer_name(INVALID_MONTH_NAME) is None
    assert not is_organizer_name(INVALID_MONTH_NAME)


def test_fold_apply_stays_opt_in() -> None:
    ops = (PACKAGE_ROOT / "docs" / "ops.md").read_text(encoding="utf-8")
    adr = (
        PACKAGE_ROOT / "docs" / "adr" / "0026-leftover-fold-is-dry-run-after-stamp.md"
    ).read_text(encoding="utf-8")
    assert "dry-run" in adr.lower()
    assert "--apply" in ops or "dry-run" in ops.lower()
