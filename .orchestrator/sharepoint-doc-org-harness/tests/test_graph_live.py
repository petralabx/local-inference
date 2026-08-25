from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
import yaml

from harness.cli import main as cli_main
from harness.config import PACKAGE_ROOT, load_config
from harness.graph.auth import acquire_delegated_token
from harness.graph.drive_client import FakeGraphDriveClient, GraphOfflineError, ORGANIZER_COLUMNS
from harness.graph.factory import resolve_graph_client
from harness.graph.live_client import (
    LiveGraphDriveClient,
    library_relative_path,
    parse_site_url,
)
from harness.jobs.stamp import StampReport, iter_stamp_files, run_stamp
from harness.journal.store import ActionJournal


SITE_ID = "petrasoap.sharepoint.com,site-guid,web-guid"
DRIVE_ID = "b!drive"
LIST_ID = "list-guid"
COLUMN_ID = "col-guid"
CT_ID = "0x0101"
ITEM_ID = "item-99"
LIST_ITEM_ID = "42"


def _cfg(tmp_path: Path, root: Path, **graph_over):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    raw.setdefault("graph", {}).update(graph_over)
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(p)


class GraphFixture:
    """In-memory Graph for LiveGraphDriveClient tests. No FileLeafRef $filter."""

    def __init__(self, sync_root: Path) -> None:
        self.sync_root = sync_root
        self.requests: list[tuple[str, str]] = []
        self.columns = {
            "OrganizerParty": {
                "id": "c1",
                "name": "OrganizerParty",
                "displayName": "Party",
                "indexed": True,
            },
            "OrganizerPrefix": {
                "id": "c2",
                "name": "OrganizerPrefix",
                "displayName": "Prefix",
                "indexed": True,
            },
            "OrganizerHome": {
                "id": "c3",
                "name": "OrganizerHome",
                "displayName": "Home",
                "indexed": True,
            },
        }
        self.ct_columns = set(self.columns)
        self.fields: dict[str, dict[str, str]] = {}
        self.children: dict[str, list[dict]] = {}

    def add_file(self, rel: str, *, list_item_id: str = LIST_ITEM_ID) -> None:
        name = Path(rel).name
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        self.children.setdefault(parent, []).append(
            {
                "id": f"file-{rel}",
                "name": name,
                "file": {},
                "sharepointIds": {"listItemId": list_item_id, "listId": LIST_ID},
            }
        )
        folder = parent
        while folder:
            grand = str(Path(folder).parent).replace("\\", "/")
            if grand == ".":
                grand = ""
            names = {c["name"] for c in self.children.get(grand, [])}
            if Path(folder).name not in names:
                self.children.setdefault(grand, []).append(
                    {"id": f"dir-{folder}", "name": Path(folder).name, "folder": {}}
                )
            folder = grand

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append((request.method, url))
        if "FileLeafRef" in url:
            return httpx.Response(400, json={"error": {"message": "throttled FileLeafRef"}})
        parsed = urlparse(url)
        path = parsed.path
        method = request.method.upper()

        if method == "GET" and path.endswith("/sites/petrasoap.sharepoint.com:/sites/VincePersonal"):
            return httpx.Response(200, json={"id": SITE_ID})
        if method == "GET" and path.endswith(f"/sites/{SITE_ID}/drive"):
            return httpx.Response(
                200,
                json={"id": DRIVE_ID, "sharePointIds": {"listId": LIST_ID}},
            )
        if method == "GET" and path.endswith(f"/sites/{SITE_ID}/columns"):
            return httpx.Response(200, json={"value": list(self.columns.values())})
        if method == "POST" and path.endswith(f"/sites/{SITE_ID}/columns"):
            body = json.loads(request.content or b"{}")
            name = body.get("name")
            row = {
                "id": COLUMN_ID,
                "name": name,
                "displayName": body.get("displayName"),
                "indexed": body.get("indexed", True),
            }
            self.columns[name] = row
            return httpx.Response(201, json=row)
        if method == "GET" and path.endswith(f"/sites/{SITE_ID}/contentTypes"):
            return httpx.Response(
                200,
                json={"value": [{"id": CT_ID, "name": "Document"}]},
            )
        if method == "GET" and "/contentTypes/" in path and path.endswith("/columns"):
            return httpx.Response(
                200,
                json={"value": [{"name": n} for n in sorted(self.ct_columns)]},
            )
        if method == "POST" and "/contentTypes/" in path and path.endswith("/columns"):
            return httpx.Response(201, json={"name": "added"})
        if method == "GET" and "/root:/" in path and path.endswith(":/children"):
            rel = _root_path(path, suffix=":/children")
            return httpx.Response(200, json={"value": list(self.children.get(rel, []))})
        if method == "GET" and path.endswith(f"/drives/{DRIVE_ID}/root/children"):
            return httpx.Response(200, json={"value": list(self.children.get("", []))})
        if method == "GET" and "/root:/" in path:
            rel = _root_path(path, suffix="")
            parent = str(Path(rel).parent).replace("\\", "/")
            if parent == ".":
                parent = ""
            name = Path(rel).name
            for child in self.children.get(parent, []):
                if child.get("name") == name:
                    return httpx.Response(200, json=child)
            return httpx.Response(404, json={"error": {"message": "not found"}})
        if method == "PATCH" and "/fields" in path:
            body = json.loads(request.content or b"{}")
            item_key = path
            self.fields[item_key] = {k: str(v) for k, v in body.items()}
            return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": {"message": path}})


def _root_path(url_path: str, suffix: str) -> str:
    marker = "/root:/"
    idx = url_path.index(marker) + len(marker)
    rest = url_path[idx:]
    if suffix and rest.endswith(suffix):
        rest = rest[: -len(suffix)]
    return unquote(rest.lstrip("/"))


def _live(tmp_path: Path, root: Path, fixture: GraphFixture) -> LiveGraphDriveClient:
    transport = httpx.MockTransport(fixture.handler)
    http = httpx.Client(transport=transport)
    return LiveGraphDriveClient(
        token_provider=lambda: "test-token",
        site_url="https://petrasoap.sharepoint.com/sites/VincePersonal",
        library="Documents",
        sync_root=root,
        http=http,
    )


def test_parse_site_and_library_relative(tmp_path: Path) -> None:
    host, path = parse_site_url("https://petrasoap.sharepoint.com/sites/VincePersonal")
    assert host == "petrasoap.sharepoint.com"
    assert path == "/sites/VincePersonal"
    root = tmp_path / "Vince Personal - Documents"
    rel = library_relative_path(str(root / "05_Personal" / "a.pdf"), root)
    assert rel == "05_Personal/a.pdf"


def test_resolve_graph_client_offline_without_credentials(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    root.mkdir()
    cfg = _cfg(tmp_path, root)
    assert acquire_delegated_token(cfg.graph, interactive=False) is None
    assert resolve_graph_client(cfg, interactive=False) is None


def test_resolve_graph_client_disabled(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    root.mkdir()
    cfg = _cfg(tmp_path, root, enabled=False)
    assert resolve_graph_client(cfg, token_provider=lambda: "x") is None


def test_resolve_graph_client_live_when_token_provider(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    root.mkdir()
    cfg = _cfg(tmp_path, root)
    client = resolve_graph_client(cfg, token_provider=lambda: "x")
    assert isinstance(client, LiveGraphDriveClient)
    client.close()


def test_live_client_stamps_via_path_not_fileleafref(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    dest = root / "05_Personal" / "Home"
    dest.mkdir(parents=True)
    src = dest / "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
    src.write_bytes(b"%PDF-live")
    fixture = GraphFixture(root)
    fixture.add_file("05_Personal/Home/" + src.name)
    client = _live(tmp_path, root, fixture)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    cfg = _cfg(tmp_path, root)
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-live.json",
        graph=client,
        limit=1,
    )
    assert report.columns_written == 1
    assert fixture.fields
    urls = " ".join(url for _m, url in fixture.requests)
    assert "FileLeafRef" not in urls
    assert "/root:/" in urls
    fields = next(iter(fixture.fields.values()))
    assert fields["Title"] == "Happy Yards Garden Clean Up Quote"
    assert fields["OrganizerParty"] == "Happy Yards"
    assert fields["OrganizerPrefix"] == "INV"
    assert fields["OrganizerHome"] == "05_Personal"
    for col in ORGANIZER_COLUMNS:
        stored = client.ensure_site_column(
            name=col.name, display_name=col.display_name, indexed=True
        )
        assert stored["displayName"] == col.display_name
        assert stored["indexed"] is True
        assert stored["scope"] == "site"
    journal.close()
    client.close()


def test_live_folder_walk_pages_children(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    root.mkdir()
    fixture = GraphFixture(root)
    fixture.add_file("05_Personal/a.pdf", list_item_id="1")
    fixture.add_file("05_Personal/nested/b.pdf", list_item_id="2")
    client = _live(tmp_path, root, fixture)
    walked = list(client.walk_folder("05_Personal"))
    names = {row["name"] for row in walked}
    assert names == {"a.pdf", "b.pdf"}
    urls = [url for _m, url in fixture.requests]
    assert any("/children" in u for u in urls)
    assert all("FileLeafRef" not in u for u in urls)
    client.close()


def test_live_offline_error_skips_columns(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    dest = root / "05_Personal"
    dest.mkdir(parents=True)
    src = dest / "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
    src.write_bytes(b"%PDF-off")

    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    http = httpx.Client(transport=httpx.MockTransport(boom))
    client = LiveGraphDriveClient(
        token_provider=lambda: "x",
        site_url="https://petrasoap.sharepoint.com/sites/VincePersonal",
        sync_root=root,
        http=http,
    )
    journal = ActionJournal(tmp_path / "j.sqlite3")
    cfg = _cfg(tmp_path, root)
    report = run_stamp(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "stamp-live-off.json",
        graph=client,
    )
    assert report.columns_written == 0
    assert report.columns_skipped >= 1
    journal.close()
    client.close()


def test_folder_walk_skips_leftover_trees_secrets_and_code(tmp_path: Path) -> None:
    root = tmp_path / "sp"
    home = root / "04_Admin" / "IT"
    leftover = root / "artifacts" / "old"
    command = root / "Command Center"
    home.mkdir(parents=True)
    leftover.mkdir(parents=True)
    command.mkdir(parents=True)
    keep = home / "2026-08-18_GEN_Keep Memo_v01.pdf"
    keep.write_bytes(b"keep")
    (leftover / "dump.pdf").write_bytes(b"dump")
    (command / "note.pdf").write_bytes(b"cc")
    (home / ".ssh").mkdir()
    (home / ".ssh" / "id_rsa").write_text("SECRET", encoding="utf-8")
    code = home / "node_modules" / "pkg"
    code.mkdir(parents=True)
    (code / "index.js").write_text("1", encoding="utf-8")
    capture = root / "00_Inbox" / "_from_mail"
    capture.mkdir(parents=True)
    (capture / "mail.pdf").write_bytes(b"mail")
    walked = list(iter_stamp_files(root, ["**/node_modules/**"]))
    assert keep in walked
    assert all("artifacts" not in p.parts for p in walked)
    assert all("Command Center" not in p.parts for p in walked)
    assert all(p.name != "id_rsa" for p in walked)
    assert all("node_modules" not in p.parts for p in walked)
    assert all("_from_mail" not in p.parts for p in walked)


def test_fake_walk_folder_and_offline(tmp_path: Path) -> None:
    graph = FakeGraphDriveClient()
    graph.item_fields["05_Personal/a.pdf"] = {"Title": "A"}
    graph.item_fields["artifacts/skip.pdf"] = {"Title": "no"}
    assert list(graph.walk_folder("05_Personal")) == ["05_Personal/a.pdf"]
    offline = FakeGraphDriveClient(online=False)
    try:
        offline.walk_folder("05_Personal")
        raised = False
    except GraphOfflineError:
        raised = True
    else:
        # walk_folder yields; force consume
        raised = False
    if not raised:
        try:
            list(offline.walk_folder("05_Personal"))
            assert False, "expected GraphOfflineError"
        except GraphOfflineError:
            raised = True
    assert raised


def test_cli_stamp_passes_live_client_when_factory_returns(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "sp"
    dest = root / "05_Personal"
    dest.mkdir(parents=True)
    src = dest / "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
    src.write_bytes(b"%PDF-cli")
    cfg = _cfg(tmp_path, root)
    graph = FakeGraphDriveClient()
    captured: dict = {}

    def fake_resolve(_cfg, **_kwargs):
        return graph

    def fake_stamp(**kwargs):
        captured.update(kwargs)
        report = StampReport(
            run_id="cli",
            started_at="t",
            finished_at="t",
            scanned=1,
            stamped=1,
        )
        report.write(kwargs["report_path"])
        return report

    monkeypatch.setattr(cli_main, "resolve_graph_client", fake_resolve)
    monkeypatch.setattr("harness.jobs.stamp.run_stamp", fake_stamp)
    code = cli_main.main(
        [
            "--config",
            str(tmp_path / "cfg.yaml"),
            "stamp",
            "--report",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == 0
    assert captured["graph"] is graph
    assert cfg.graph.upn == "vince@petrasoap.com"


def test_cli_digest_and_relabel_pass_graph(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "sp"
    (root / "00_Inbox").mkdir(parents=True)
    _cfg(tmp_path, root)
    graph = FakeGraphDriveClient()
    seen: list[object] = []

    def fake_resolve(_cfg, **_kwargs):
        return graph

    def fake_digest(**kwargs):
        seen.append(kwargs.get("graph"))
        from harness.jobs.digest import DigestReport

        report = DigestReport(run_id="d", started_at="t", finished_at="t")
        report.write(kwargs["report_path"])
        return report

    def fake_relabel(**kwargs):
        seen.append(kwargs.get("graph"))
        from harness.jobs.relabel import RelabelReport

        report = RelabelReport(run_id="r", started_at="t", finished_at="t")
        report.write(kwargs["report_path"])
        return report

    monkeypatch.setattr(cli_main, "resolve_graph_client", fake_resolve)
    monkeypatch.setattr("harness.jobs.digest.run_digest", fake_digest)
    monkeypatch.setattr("harness.jobs.relabel.run_relabel", fake_relabel)
    assert (
        cli_main.main(
            ["--config", str(tmp_path / "cfg.yaml"), "digest", "--report", str(tmp_path / "d.json")]
        )
        == 0
    )
    assert (
        cli_main.main(
            ["--config", str(tmp_path / "cfg.yaml"), "relabel", "--report", str(tmp_path / "r.json")]
        )
        == 0
    )
    assert seen == [graph, graph]


def test_cli_stamp_passes_none_when_offline(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "sp"
    root.mkdir()
    _cfg(tmp_path, root)
    captured: dict = {}

    def fake_resolve(_cfg, **_kwargs):
        return None

    def fake_stamp(**kwargs):
        captured.update(kwargs)
        report = StampReport(run_id="off", started_at="t", finished_at="t")
        report.write(kwargs["report_path"])
        return report

    monkeypatch.setattr(cli_main, "resolve_graph_client", fake_resolve)
    monkeypatch.setattr("harness.jobs.stamp.run_stamp", fake_stamp)
    code = cli_main.main(
        [
            "--config",
            str(tmp_path / "cfg.yaml"),
            "stamp",
            "--report",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == 0
    assert captured["graph"] is None


def test_cli_graph_login_help() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "harness.cli.main", "graph-login", "--help"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "device-code" in proc.stdout.lower() or "delegated" in proc.stdout.lower()


def test_docs_record_delegated_graph_decision() -> None:
    adr = (PACKAGE_ROOT / "docs" / "adr" / "0026-delegated-msal-graph-on-vta.md").read_text(
        encoding="utf-8"
    )
    ops = (PACKAGE_ROOT / "docs" / "ops.md").read_text(encoding="utf-8")
    for text in (adr, ops):
        assert "device-code" in text.lower()
        assert "vince@petrasoap.com" in text
        assert "FileLeafRef" in text
    assert "app-only" in adr.lower()
    assert "graph-login" in ops
