from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
import yaml

from harness.cli.main import main
from harness.config import PACKAGE_ROOT, load_config
from harness.graph.folder_lister import (
    FakeGraphFolderLister,
    FakeSharePointRestLister,
    FolderTree,
    GraphDriveFolderLister,
    SharePointRestFolderLister,
    build_live_lister,
    lister_from_cassette,
)
from harness.identity import content_hash
from harness.jobs.sync_audit import DEFAULT_REPORT_REL, default_report_path, run_sync_audit


def _cfg_for_root(tmp_path: Path, root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p), p


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_fixture(root: Path) -> dict[str, Path]:
    """Small Vince Personal tree: local-only, match, rehome, skip, hash-differ."""
    expenses = root / "05_Personal" / "Expenses"
    expenses.mkdir(parents=True)
    clients = root / "01_Clients_Projects"
    clients.mkdir(parents=True)
    inbox = root / "00_Inbox"
    inbox.mkdir(parents=True)
    code = root / "04_Admin" / "node_modules" / "pkg"
    code.mkdir(parents=True)
    secret_dir = root / "04_Admin" / ".ssh"
    secret_dir.mkdir(parents=True)

    files = {
        "local_only": expenses / "2024-03-01_HappyYards-1.pdf",
        "matched": expenses / "2024-03-01_HappyYards-2.pdf",
        "rehomed": expenses / "rehomed-receipt.pdf",
        "keep": clients / "keep.pdf",
        "secret": secret_dir / "id_ed25519",
        "pem": expenses / "clawdbot.pem",
        "code": code / "index.js",
    }
    files["local_only"].write_bytes(b"happy-yards-local-only")
    files["matched"].write_bytes(b"happy-yards-on-both")
    files["rehomed"].write_bytes(b"rehomed-bytes")
    files["keep"].write_bytes(b"local-keep")
    files["secret"].write_text("SECRET", encoding="utf-8")
    files["pem"].write_text("-----BEGIN", encoding="utf-8")
    files["code"].write_text("module.exports=1", encoding="utf-8")
    return files


def _server_tree(files: dict[str, Path]) -> FolderTree:
    tree = FolderTree()
    tree.add_file(
        "05_Personal/Expenses/2024-03-01_HappyYards-2.pdf",
        size=files["matched"].stat().st_size,
        sha256=content_hash(files["matched"]),
    )
    tree.add_file(
        "00_Inbox/rehomed-receipt.pdf",
        size=7,
        sha256=_sha(b"rehomed-bytes"),
    )
    tree.add_file(
        "01_Clients_Projects/keep.pdf",
        size=11,
        sha256=_sha(b"server-keep"),
    )
    tree.add_file("06_Reference/server-only.pdf", size=4, sha256=_sha(b"srv"))
    tree.add_file("04_Admin/node_modules/pkg/index.js", size=16, sha256=_sha(b"js"))
    tree.add_file("05_Personal/Expenses/clawdbot.pem", size=10, sha256=_sha(b"pem"))
    tree.ensure_folder("06_Reference")
    return tree


def test_default_report_path_is_under_harness_data_reports() -> None:
    path = default_report_path()
    assert path == PACKAGE_ROOT / DEFAULT_REPORT_REL
    assert path.as_posix().endswith("data/reports/sync-audit.json")


def test_graph_fake_reports_local_server_path_and_hash_mismatches(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    lister = FakeGraphFolderLister(_server_tree(files))
    report_path = tmp_path / "reports" / "sync-audit.json"
    before = {p: p.read_bytes() for p in files.values()}

    report = run_sync_audit(
        cfg=cfg,
        lister=lister,
        report_path=report_path,
        hashes=True,
    )

    assert report_path.is_file()
    assert report.backend == "fake-graph"
    assert report.folders_walked >= 3
    local_only = {row["path"] for row in report.local_only}
    server_only = {row["path"] for row in report.server_only}
    assert "05_Personal/Expenses/2024-03-01_HappyYards-1.pdf" in local_only
    assert "06_Reference/server-only.pdf" in server_only
    assert not any("clawdbot.pem" in row["path"] for row in report.local_only)
    assert not any("node_modules" in row["path"] for row in report.local_only)
    assert not any("id_ed25519" in row["path"] for row in report.local_only)
    assert not any("node_modules" in row["path"] for row in report.server_only)
    mismatches = {(row["local_path"], row["server_path"]) for row in report.path_mismatches}
    assert (
        "05_Personal/Expenses/rehomed-receipt.pdf",
        "00_Inbox/rehomed-receipt.pdf",
    ) in mismatches
    hash_paths = {row["path"] for row in report.hash_mismatches}
    assert "01_Clients_Projects/keep.pdf" in hash_paths
    # Report only: local bytes unchanged, nothing renamed or uploaded.
    for path, payload in before.items():
        assert path.exists()
        assert path.read_bytes() == payload
    assert lister.calls[0] == ""
    assert "05_Personal" in lister.calls
    assert "05_Personal/Expenses" in lister.calls
    assert all("$filter" not in call.lower() for call in lister.calls)


def test_rest_fake_matches_graph_inventory(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    tree = _server_tree(files)
    graph = FakeGraphFolderLister(tree)
    rest = FakeSharePointRestLister(tree)
    graph_report = run_sync_audit(
        cfg=cfg, lister=graph, report_path=tmp_path / "g.json", hashes=True
    )
    rest_report = run_sync_audit(
        cfg=cfg, lister=rest, report_path=tmp_path / "r.json", hashes=True
    )
    assert graph_report.backend == "fake-graph"
    assert rest_report.backend == "fake-rest"
    assert {row["path"] for row in graph_report.local_only} == {
        row["path"] for row in rest_report.local_only
    }
    assert {row["path"] for row in graph_report.server_only} == {
        row["path"] for row in rest_report.server_only
    }
    assert graph_report.path_mismatches == rest_report.path_mismatches
    assert graph_report.hash_mismatches == rest_report.hash_mismatches
    assert rest.file_calls
    assert rest.folder_calls
    assert rest.file_calls == rest.folder_calls
    assert len(rest.file_calls) == rest_report.folders_walked


def test_dry_run_skips_hashes(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    report = run_sync_audit(
        cfg=cfg,
        lister=FakeGraphFolderLister(_server_tree(files)),
        report_path=tmp_path / "dry.json",
        dry_run=True,
        hashes=True,
    )
    assert report.dry_run is True
    assert report.hashes is False
    assert report.hash_mismatches == []
    assert "dry_run" in report.notes
    assert "hashes_skipped_dry_run" in report.notes
    assert "report_only" in report.notes
    assert any(row["path"].endswith("HappyYards-1.pdf") for row in report.local_only)


def test_only_limits_walk_to_subtree(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    report = run_sync_audit(
        cfg=cfg,
        lister=FakeGraphFolderLister(_server_tree(files)),
        report_path=tmp_path / "only.json",
        only=["05_Personal"],
    )
    local_only = {row["path"] for row in report.local_only}
    server_only = {row["path"] for row in report.server_only}
    assert any(p.startswith("05_Personal/") for p in local_only)
    assert "06_Reference/server-only.pdf" not in server_only
    assert "only=05_Personal" in report.notes


def test_oserror_22_on_folder_is_recorded_not_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    cfg, _ = _cfg_for_root(tmp_path, root)
    real_scandir = os.scandir

    def selective(path):  # type: ignore[no-untyped-def]
        if Path(path).name == "Expenses":
            raise OSError(22, "Invalid argument")
        return real_scandir(path)

    monkeypatch.setattr("harness.jobs.sync_audit.os.scandir", selective)
    report = run_sync_audit(
        cfg=cfg,
        lister=FakeGraphFolderLister(_server_tree(files)),
        report_path=tmp_path / "oserror.json",
    )
    assert any("OSError:22" in row for row in report.errors)
    assert "06_Reference/server-only.pdf" in {row["path"] for row in report.server_only}


def test_live_graph_walks_children_without_filter(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = unquote(str(request.url))
        seen.append(url)
        assert "$filter" not in url.lower()
        assert request.method == "GET"
        path = unquote(request.url.path)
        if path.endswith("/root/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "f1", "name": "05_Personal", "folder": {"childCount": 1}},
                    ]
                },
            )
        if "/root:/05_Personal:/children" in path or path.endswith("/root:/05_Personal:/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "i1",
                            "name": "only-on-server.pdf",
                            "size": 3,
                            "file": {"hashes": {"sha256Hash": "aa" * 32}},
                        }
                    ]
                },
            )
        return httpx.Response(404, json={"error": {"code": "itemNotFound"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    lister = GraphDriveFolderLister(drive_id="drive-1", token="t", client=client)
    root = tmp_path / "sp"
    root.mkdir()
    (root / "05_Personal").mkdir()
    cfg, _ = _cfg_for_root(tmp_path, root)
    report = run_sync_audit(cfg=cfg, lister=lister, report_path=tmp_path / "live-graph.json")
    assert report.backend == "graph"
    assert any(row["path"] == "05_Personal/only-on-server.pdf" for row in report.server_only)
    assert any("root/children" in url or "root:/05_Personal:/children" in unquote(url) for url in seen)
    assert all("$filter" not in url.lower() for url in seen)


def test_live_rest_uses_get_folder_by_server_relative_url(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = unquote(str(request.url))
        seen.append(url)
        assert "$filter" not in url.lower()
        assert "GetFolderByServerRelativeUrl" in url
        assert request.method == "GET"
        if url.endswith("/Files") or "/Files?" in url:
            if "05_Personal" in url:
                return httpx.Response(200, json={"value": [{"Name": "rest.pdf", "Length": 2}]})
            return httpx.Response(200, json={"value": []})
        if "05_Personal" in url:
            return httpx.Response(200, json={"value": []})
        return httpx.Response(200, json={"value": [{"Name": "05_Personal"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    lister = SharePointRestFolderLister(
        site_url="https://contoso.sharepoint.com/sites/VincePersonal",
        server_relative_root="/sites/VincePersonal/Shared Documents",
        token="t",
        client=client,
    )
    root = tmp_path / "sp"
    (root / "05_Personal").mkdir(parents=True)
    cfg, _ = _cfg_for_root(tmp_path, root)
    report = run_sync_audit(cfg=cfg, lister=lister, report_path=tmp_path / "live-rest.json")
    assert report.backend == "rest"
    assert any(row["path"] == "05_Personal/rest.pdf" for row in report.server_only)
    assert lister.file_calls[0] == ""
    assert "05_Personal" in lister.file_calls
    assert all("GetFolderByServerRelativeUrl" in url for url in seen)


def test_build_live_lister_requires_token() -> None:
    with pytest.raises(ValueError, match="token"):
        build_live_lister(backend="graph", token=None, drive_id="x")


def test_cli_dry_run_with_cassette(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    files = _build_fixture(root)
    _, cfg_path = _cfg_for_root(tmp_path, root)
    cassette = tmp_path / "cassette.json"
    items = [
        {"path": "05_Personal/Expenses/2024-03-01_HappyYards-2.pdf", "size": 4},
        {"path": "00_Inbox/rehomed-receipt.pdf", "size": 7},
        {"path": "01_Clients_Projects/keep.pdf", "size": 11},
        {"path": "06_Reference/server-only.pdf", "size": 4},
    ]
    cassette.write_text(json.dumps({"items": items}), encoding="utf-8")
    report_path = tmp_path / "cli-audit.json"
    rc = main(
        [
            "--config",
            str(cfg_path),
            "sync-audit",
            "--dry-run",
            "--cassette",
            str(cassette),
            "--report",
            str(report_path),
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["hashes"] is False
    assert any(row["path"].endswith("HappyYards-1.pdf") for row in payload["local_only"])
    assert files["local_only"].is_file()


def test_cli_rest_cassette_backend(tmp_path: Path) -> None:
    root = tmp_path / "Vince Personal - Documents"
    _build_fixture(root)
    _, cfg_path = _cfg_for_root(tmp_path, root)
    cassette = tmp_path / "cassette.json"
    cassette.write_text(
        json.dumps({"items": [{"path": "06_Reference/server-only.pdf", "size": 1}]}),
        encoding="utf-8",
    )
    report_path = tmp_path / "rest.json"
    rc = main(
        [
            "--config",
            str(cfg_path),
            "sync-audit",
            "--backend",
            "rest",
            "--cassette",
            str(cassette),
            "--report",
            str(report_path),
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["backend"] == "fake-rest"


def test_cli_help_documents_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["sync-audit", "--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out.lower()
    assert "dry-run" in text
    assert "upload" in text or "report" in text


def test_cli_refuses_without_lister(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("HARNESS_GRAPH_TOKEN", raising=False)
    monkeypatch.delenv("HARNESS_SP_TOKEN", raising=False)
    root = tmp_path / "sp"
    root.mkdir()
    _, cfg_path = _cfg_for_root(tmp_path, root)
    rc = main(["--config", str(cfg_path), "sync-audit", "--report", str(tmp_path / "x.json")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "folder lister" in err
    assert "never uploads" in err


def test_lister_from_cassette_roundtrip(tmp_path: Path) -> None:
    cassette = tmp_path / "c.json"
    cassette.write_text(
        json.dumps({"items": [{"path": "00_Inbox/a.txt", "size": 1, "sha256": "ab"}]}),
        encoding="utf-8",
    )
    graph = lister_from_cassette(cassette, backend="graph")
    rest = lister_from_cassette(cassette, backend="rest")
    listing = graph.list_children("00_Inbox")
    assert listing.files[0].name == "a.txt"
    assert rest.list_files("00_Inbox")[0].name == "a.txt"


def test_ops_and_readme_document_dry_run() -> None:
    ops = (PACKAGE_ROOT / "docs" / "ops.md").read_text(encoding="utf-8")
    readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    assert "sync-audit --dry-run" in ops
    assert "data/reports/sync-audit.json" in ops
    assert "python -m harness.cli.main sync-audit --dry-run" in readme


def test_cli_help_subprocess_mentions_report_only() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "harness.cli.main", "sync-audit", "--help"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    text = proc.stdout.lower()
    assert "dry-run" in text
    assert "upload" in text or "report" in text
