from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from harness.cli.main import main
from harness.config import PACKAGE_ROOT, load_config
from harness.graph.drive_client import FakeGraphDriveClient, GraphConflictError
from harness.jobs.harvest import HarvestApplyBlocked, guard_harvest_apply, run_harvest
from harness.journal.store import ActionJournal


def _cfg_for_root(tmp_path: Path, root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p), p


def _tree(root: Path) -> dict[str, Path]:
    expenses = root / "05_Personal" / "Expenses"
    expenses.mkdir(parents=True)
    code = root / "04_Admin" / "node_modules" / "pkg"
    code.mkdir(parents=True)
    secret_dir = root / "04_Admin" / ".ssh"
    secret_dir.mkdir(parents=True)
    files = {
        "doc": expenses / "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf",
        "secret": secret_dir / "id_ed25519",
        "code": code / "index.js",
        "pem": expenses / "clawdbot.pem",
    }
    files["doc"].write_bytes(b"%PDF-local-only")
    files["secret"].write_text("SECRET", encoding="utf-8")
    files["code"].write_text("module.exports=1", encoding="utf-8")
    files["pem"].write_text("-----BEGIN", encoding="utf-8")
    return files


def test_fake_upload_simple_creates_parents_skips_identical_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    files = _tree(root)
    graph = FakeGraphDriveClient()
    rel = "05_Personal/Expenses/" + files["doc"].name
    first = graph.upload_file(files["doc"], rel)
    assert first["status"] == "uploaded"
    assert first["mode"] == "simple"
    assert rel in graph.server_files
    assert "05_Personal/Expenses" in graph.folders
    skipped = graph.upload_file(files["doc"], rel)
    assert skipped["status"] == "skipped_identical"
    files["doc"].write_bytes(b"%PDF-local-only-CHANGED")
    with pytest.raises(GraphConflictError):
        graph.upload_file(files["doc"], rel)
    replaced = graph.upload_file(files["doc"], rel, replace=True)
    assert replaced["status"] == "replaced"


def test_fake_session_mode_when_over_threshold(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    dest = root / "05_Personal"
    dest.mkdir(parents=True)
    src = dest / "big.bin"
    src.write_bytes(b"x" * 32)
    graph = FakeGraphDriveClient(simple_upload_max_bytes=8)
    result = graph.upload_file(src, "05_Personal/big.bin")
    assert result["mode"] == "session"
    assert result["status"] == "uploaded"


def test_harvest_dry_run_plans_and_skips_secrets_code(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    files = _tree(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    local_only = [
        {"path": "05_Personal/Expenses/" + files["doc"].name, "size": files["doc"].stat().st_size},
        {"path": "04_Admin/.ssh/id_ed25519", "size": 6},
        {"path": "04_Admin/node_modules/pkg/index.js", "size": 16},
        {"path": "05_Personal/Expenses/clawdbot.pem", "size": 10},
    ]
    report = run_harvest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "harvest-dry.json",
        graph=graph,
        apply=False,
        local_only=local_only,
    )
    assert report.dry_run is True
    assert report.apply is False
    assert report.uploaded == 0
    assert report.planned == 1
    assert report.skipped_secret >= 1
    assert report.skipped_code >= 1
    assert graph.server_files == {}
    assert files["doc"].read_bytes() == b"%PDF-local-only"
    journal.close()


def test_harvest_apply_uploads_then_stamps_on_linux(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    files = _tree(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    graph = FakeGraphDriveClient()
    rel = "05_Personal/Expenses/" + files["doc"].name
    report = run_harvest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "harvest-apply.json",
        graph=graph,
        apply=True,
        local_only=[{"path": rel, "size": files["doc"].stat().st_size}],
    )
    assert sys.platform != "win32"
    assert report.apply is True
    assert report.uploaded == 1
    assert report.stamped >= 1
    assert report.columns_written >= 1
    assert rel in graph.server_files
    fields = graph.item_fields[str(files["doc"])]
    assert fields["Title"] == "Happy Yards Garden Clean Up Quote"
    assert fields["OrganizerParty"] == "Happy Yards"
    assert fields["OrganizerPrefix"] == "INV"
    assert fields["OrganizerHome"] == "05_Personal"
    journal.close()


def test_harvest_reads_audit_report(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    files = _tree(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    journal = ActionJournal(Path(cfg.journal_path))
    rel = "05_Personal/Expenses/" + files["doc"].name
    audit = tmp_path / "sync-audit.json"
    audit.write_text(
        json.dumps({"local_only": [{"path": rel, "name": files["doc"].name, "size": 4}]}),
        encoding="utf-8",
    )
    report = run_harvest(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "from-audit.json",
        graph=FakeGraphDriveClient(),
        apply=False,
        audit_report=audit,
    )
    assert report.planned == 1
    journal.close()


def test_guard_harvest_apply_allows_graph_only_on_linux() -> None:
    guard_harvest_apply(apply=True, would_move_local=False)
    with pytest.raises(HarvestApplyBlocked):
        guard_harvest_apply(apply=True, would_move_local=True)


def test_cli_harvest_help() -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "harness.cli.main", "harvest", "--help"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    text = proc.stdout.lower()
    assert "dry-run" in text
    assert "--apply" in proc.stdout
    assert "upload" in text


def test_cli_harvest_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    files = _tree(root)
    _, cfg_path = _cfg_for_root(tmp_path, root)
    rel = "05_Personal/Expenses/" + files["doc"].name
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"local_only": [{"path": rel, "size": 4}]}), encoding="utf-8")
    report_path = tmp_path / "cli-harvest.json"
    rc = main(
        [
            "--config",
            str(cfg_path),
            "harvest",
            "--dry-run",
            "--audit-report",
            str(audit),
            "--report",
            str(report_path),
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["apply"] is False
    assert payload["planned"] == 1
    assert payload["uploaded"] == 0
    assert files["doc"].is_file()
