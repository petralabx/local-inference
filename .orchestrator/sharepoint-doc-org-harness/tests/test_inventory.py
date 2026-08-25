from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness.actions.inventory import (
    STATUS_ALREADY,
    STATUS_CANDIDATE,
    STATUS_SKIP_CODE,
    STATUS_SKIP_SECRET,
    classify_file,
    is_under,
    load_inventory_roots,
)
from harness.config import PACKAGE_ROOT, load_config
from harness.jobs.inventory import run_inventory
from harness.journal.store import ActionJournal


def _cfg_for_root(tmp_path: Path, sync_root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(sync_root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(path), path


def _write(path: Path, data: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _fixture_roots(tmp_path: Path) -> dict[str, Path]:
    vp = tmp_path / "Vince Personal - Documents"
    redirected = _write(vp / "00_Inbox" / "_from_desktop" / "already.pdf", b"in-vp")
    personal = tmp_path / "OneDrive"
    leftover_doc = _write(personal / "Documents" / "tax.pdf", b"personal-tax")
    secret = _write(personal / ".ssh" / "id_rsa", "SECRET-KEY")
    env_file = _write(personal / ".env", "TOKEN=nope")
    _write(personal / "node_modules" / "pkg" / "index.js", "module.exports = 1")
    _write(personal / "desktop.ini", "[.ShellClassInfo]")
    petra = tmp_path / "OneDrive - Petra Hygienic Systems Int Ltd"
    petra_archive = _write(petra / "09_Archive" / "old.pdf", b"petra-old")
    nested_vp = petra / "Vince Personal - Documents"
    nested_vp.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(vp, nested_vp, target_is_directory=True)
    downloads = tmp_path / "Downloads"
    invoice = _write(downloads / "invoice.pdf", b"second-downloads")
    pem = _write(downloads / "clawdbot.pem", "SECRET-PEM")
    canonical = tmp_path / "local-inference-canonical"
    _write(canonical / ".git" / "HEAD", "ref: refs/heads/main")
    _write(canonical / "src" / "main.py", "print(1)\n")
    git_repo = tmp_path / "old-laptop" / "notes-repo"
    _write(git_repo / ".git" / "HEAD", "ref: refs/heads/main")
    _write(git_repo / "readme.md", "do-not-file")
    desktop = tmp_path / "Desktop"
    os.symlink(vp / "00_Inbox" / "_from_desktop", desktop, target_is_directory=True)
    return {
        "vp": vp,
        "redirected": redirected,
        "personal": personal,
        "leftover_doc": leftover_doc,
        "secret": secret,
        "env_file": env_file,
        "petra": petra,
        "petra_archive": petra_archive,
        "downloads": downloads,
        "invoice": invoice,
        "pem": pem,
        "canonical": canonical,
        "git_repo": git_repo,
        "desktop": desktop,
        "old_laptop": tmp_path / "old-laptop",
    }


def test_classify_helpers_keep_vince_personal_visible(tmp_path: Path) -> None:
    vp = tmp_path / "Vince Personal - Documents"
    inside = _write(vp / "00_Inbox" / "note.pdf", b"x")
    outside = _write(tmp_path / "OneDrive" / "note.pdf", b"y")
    assert is_under(inside, vp)
    assert is_under(vp, vp)
    assert not is_under(outside, vp)
    status = classify_file(
        inside,
        sync_root=vp,
        exclude_globs=["**/node_modules/**"],
        extra_tokens=["local-inference-canonical"],
    )
    assert status == STATUS_ALREADY


def test_inventory_classifies_fixture_roots_without_copying(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    journal = ActionJournal(tmp_path / "j.sqlite3")
    before_vp = {p.resolve() for p in fx["vp"].rglob("*") if p.is_file()}
    leftover_bytes = fx["leftover_doc"].read_bytes()
    invoice_bytes = fx["invoice"].read_bytes()
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "inventory.json",
            roots=[
                str(fx["personal"]),
                str(fx["petra"]),
                str(fx["downloads"]),
                str(fx["canonical"]),
                str(fx["old_laptop"]),
                str(fx["desktop"]),
                str(fx["vp"]),
            ],
        )
        actions = journal.list_actions(report.run_id)
    finally:
        journal.close()

    assert report.copied is False
    assert report.uploaded is False
    assert "report_only" in report.notes
    assert actions == []
    assert fx["leftover_doc"].read_bytes() == leftover_bytes
    assert fx["invoice"].read_bytes() == invoice_bytes
    assert fx["secret"].exists()
    after_vp = {p.resolve() for p in fx["vp"].rglob("*") if p.is_file()}
    assert after_vp == before_vp
    assert not (fx["vp"] / "tax.pdf").exists()
    assert not (fx["vp"] / "00_Inbox" / "invoice.pdf").exists()

    by_name = {Path(row["path"]).name: row["status"] for row in report.files}
    assert by_name["tax.pdf"] == STATUS_CANDIDATE
    assert by_name["invoice.pdf"] == STATUS_CANDIDATE
    assert by_name["old.pdf"] == STATUS_CANDIDATE
    assert by_name["already.pdf"] == STATUS_ALREADY
    assert by_name["id_rsa"] == STATUS_SKIP_SECRET
    assert by_name[".env"] == STATUS_SKIP_SECRET
    assert by_name["clawdbot.pem"] == STATUS_SKIP_SECRET
    assert "desktop.ini" not in by_name
    assert "index.js" not in by_name
    assert "main.py" not in by_name
    assert "readme.md" not in by_name

    statuses = {row["status"] for row in report.files}
    assert statuses <= {STATUS_CANDIDATE, STATUS_SKIP_CODE, STATUS_SKIP_SECRET, STATUS_ALREADY}
    assert report.candidate_to_consume >= 3
    assert report.skip_secret >= 3
    assert report.skip_code >= 3
    assert report.already_in_vince_personal >= 1
    assert report.skipped_noise >= 1

    candidates = [row for row in report.files if row["status"] == STATUS_CANDIDATE]
    assert all(row["sha256"] for row in candidates)
    trees = [row for row in report.files if row["kind"] == "tree"]
    tree_names = {Path(row["path"]).name for row in trees}
    assert "local-inference-canonical" in tree_names
    assert "notes-repo" in tree_names
    assert "node_modules" in tree_names
    assert all(row["status"] == STATUS_SKIP_CODE for row in trees)

    payload = json.loads((tmp_path / "inventory.json").read_text(encoding="utf-8"))
    assert payload["copied"] is False
    assert payload["uploaded"] is False
    assert payload["candidate_to_consume"] == report.candidate_to_consume


def test_inventory_does_not_scan_vince_personal_unless_listed(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "only-leftover.json",
            roots=[str(fx["downloads"])],
        )
    finally:
        journal.close()
    names = {Path(row["path"]).name for row in report.files}
    assert "invoice.pdf" in names
    assert "already.pdf" not in names
    assert "tax.pdf" not in names
    assert report.already_in_vince_personal == 0


def test_inventory_requires_roots(tmp_path: Path) -> None:
    cfg, _ = _cfg_for_root(tmp_path, tmp_path / "vp")
    journal = ActionJournal(tmp_path / "j.sqlite3")
    with pytest.raises(ValueError, match="at least one"):
        try:
            run_inventory(
                cfg=cfg,
                journal=journal,
                report_path=tmp_path / "unused.json",
                roots=[],
            )
        finally:
            journal.close()


def test_inventory_roots_file_and_missing_root(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    roots_file = tmp_path / "roots.yaml"
    roots_file.write_text(
        yaml.safe_dump({"roots": [str(fx["downloads"]), str(tmp_path / "missing-root")]}),
        encoding="utf-8",
    )
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "from-file.json",
            roots_file=roots_file,
        )
    finally:
        journal.close()
    assert report.missing_roots
    assert any(Path(row["path"]).name == "invoice.pdf" for row in report.files)
    assert "missing_roots" in report.notes


def test_example_roots_file_is_empty_and_cli_writes_report(tmp_path: Path) -> None:
    example = PACKAGE_ROOT / "config" / "inventory_roots.example.yaml"
    assert load_inventory_roots(example) == []
    text = example.read_text(encoding="utf-8")
    assert "Vince Personal" in text
    assert "taylorvalton" in text.lower() or "Laptop" in text

    fx = _fixture_roots(tmp_path)
    _, cfg_path = _cfg_for_root(tmp_path, fx["vp"])
    report_path = tmp_path / "cli-inventory.json"
    journal_path = tmp_path / "cli-journal.sqlite3"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness.cli.main",
            "--config",
            str(cfg_path),
            "inventory",
            "--report",
            str(report_path),
            "--root",
            str(fx["personal"]),
            "--root",
            str(fx["downloads"]),
            "--journal",
            str(journal_path),
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "candidate_to_consume=" in proc.stdout
    assert "copied=False" in proc.stdout
    data = json.loads(report_path.read_text(encoding="utf-8"))
    names = {Path(row["path"]).name for row in data["files"]}
    assert "tax.pdf" in names
    assert "invoice.pdf" in names
    assert data["copied"] is False
    empty = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness.cli.main",
            "--config",
            str(cfg_path),
            "inventory",
            "--report",
            str(tmp_path / "empty.json"),
            "--journal",
            str(journal_path),
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert empty.returncode == 2
    assert "at least one" in empty.stdout


def test_default_config_keeps_canonical_checkout_off_sharepoint() -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert "local-inference-canonical" in cfg.skip_code_path_tokens
    assert any("local-inference-canonical" in glob for glob in cfg.exclude_globs)


def test_inventory_skips_loose_code_files(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    script = _write(fx["downloads"] / "backup.ps1", "Write-Output 'no'")
    py_file = _write(fx["downloads"] / "scratch.py", "print(1)\n")
    js_file = _write(fx["personal"] / "Documents" / "app.js", "console.log(1)\n")
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "code-files.json",
            roots=[str(fx["downloads"]), str(fx["personal"])],
        )
    finally:
        journal.close()
    by_path = {row["path"]: row for row in report.files}
    assert by_path[str(script)]["status"] == STATUS_SKIP_CODE
    assert by_path[str(py_file)]["status"] == STATUS_SKIP_CODE
    assert by_path[str(js_file)]["status"] == STATUS_SKIP_CODE
    assert by_path[str(script)]["sha256"] == ""
    assert by_path[str(fx["invoice"])]["status"] == STATUS_CANDIDATE


def test_inventory_classifies_symlink_alias_to_secret(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    alias = fx["downloads"] / "notes.pdf"
    os.symlink(fx["secret"], alias)
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "symlink-secret.json",
            roots=[str(fx["downloads"])],
        )
    finally:
        journal.close()
    row = next(item for item in report.files if item["path"] == str(alias))
    assert row["status"] == STATUS_SKIP_SECRET
    assert row["sha256"] == ""
    assert fx["secret"].read_text(encoding="utf-8") == "SECRET-KEY"


def test_inventory_survives_cyclic_symlinks(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    loop_a = fx["downloads"] / "loop-a"
    loop_b = fx["downloads"] / "loop-b"
    os.symlink(loop_b, loop_a)
    os.symlink(loop_a, loop_b)
    cfg, _ = _cfg_for_root(tmp_path, fx["vp"])
    journal = ActionJournal(tmp_path / "j.sqlite3")
    try:
        report = run_inventory(
            cfg=cfg,
            journal=journal,
            report_path=tmp_path / "cycles.json",
            roots=[str(fx["downloads"])],
        )
    finally:
        journal.close()
    assert any(Path(row["path"]).name == "invoice.pdf" for row in report.files)
    assert report.copied is False


def test_inventory_cli_all_missing_roots_exits_nonzero(tmp_path: Path) -> None:
    fx = _fixture_roots(tmp_path)
    _, cfg_path = _cfg_for_root(tmp_path, fx["vp"])
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness.cli.main",
            "--config",
            str(cfg_path),
            "inventory",
            "--report",
            str(tmp_path / "missing.json"),
            "--root",
            str(tmp_path / "does-not-exist"),
            "--journal",
            str(tmp_path / "cli-journal.sqlite3"),
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stderr + proc.stdout
    assert "missing_roots=" in proc.stdout

