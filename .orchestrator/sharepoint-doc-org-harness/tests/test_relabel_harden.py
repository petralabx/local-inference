from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.config import PACKAGE_ROOT, load_config
from harness.journal.store import ActionJournal
from harness.naming import is_organizer_name, peel_rebuild_organizer_name


INVALID_MONTH_NAME = "2022-20-03_PRO_Related_Items_Import_v01.xls"
INVALID_DAY_NAME = "2022-02-30_PRO_Related Items Import_v01.xls"
VALID_LAW_NAME = "2024-02-29_INV_Happy Yards Invoice_v01.pdf"
HAPPY_YARDS_STACKED = (
    "2026-08-18_INV_2026-08-18_01_CLIENTS_PROJECTS_"
    "Happy Yards Garden Clean Up Quote_v01_v01.pdf"
)
HAPPY_YARDS_LAW = "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"


def _relabel_cfg(tmp_path: Path, root: Path):
    raw = yaml.safe_load((PACKAGE_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    raw["sharepoint_sync_root"] = str(root)
    raw["journal_path"] = str(tmp_path / "j.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(cfg_path)


def test_invalid_month_is_not_organizer_name() -> None:
    assert peel_rebuild_organizer_name(INVALID_MONTH_NAME) is None
    assert not is_organizer_name(INVALID_MONTH_NAME)
    assert peel_rebuild_organizer_name(INVALID_DAY_NAME) is None
    assert not is_organizer_name(INVALID_DAY_NAME)
    assert peel_rebuild_organizer_name(VALID_LAW_NAME) == VALID_LAW_NAME
    assert is_organizer_name(VALID_LAW_NAME)


def test_relabel_skips_telegram_and_clawdbot_cache(tmp_path: Path) -> None:
    from harness.jobs.relabel import iter_relabel_files

    root = tmp_path / "sp"
    cache = (
        root
        / "01_Clients_Projects"
        / "ClawdBot"
        / "Telegram Desktop"
        / "media"
    )
    cache.mkdir(parents=True)
    junk = cache / "photo.jpg"
    junk.write_bytes(b"telegram-cache")
    keep_dir = root / "01_Clients_Projects" / "Happy Yards"
    keep_dir.mkdir(parents=True)
    keep = keep_dir / "keep.pdf"
    keep.write_bytes(b"keep")
    files = iter_relabel_files(root, [])
    assert keep in files
    assert junk not in files
    assert all("Telegram Desktop" not in p.parts for p in files)
    assert all("ClawdBot" not in p.parts for p in files)


def test_relabel_continues_after_raising_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.jobs import relabel as relabel_mod

    root = tmp_path / "sp"
    home = root / "05_Personal" / "Expenses"
    home.mkdir(parents=True)
    boom = home / "boom-source.pdf"
    boom.write_bytes(b"raise-me")
    stacked = home / HAPPY_YARDS_STACKED
    stacked.write_bytes(b"happy-yards-stacked")

    real_process = relabel_mod.InboxSorter.process_file

    def exploding_process(self, src, **kwargs):
        if src.name == boom.name:
            raise RuntimeError("graph 404 / llm timeout stand-in")
        return real_process(self, src, **kwargs)

    monkeypatch.setattr(relabel_mod.InboxSorter, "process_file", exploding_process)

    cfg = _relabel_cfg(tmp_path, root)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    report = relabel_mod.run_relabel(
        cfg=cfg,
        journal=journal,
        report_path=tmp_path / "relabel-harden.json",
        llm_caller=lambda **_: '{"error":"peel must not call llm"}',
    )
    actions = journal.list_actions(report.run_id)
    journal.close()

    assert report.scanned == 2
    assert report.errors == 1
    assert report.peeled == 1
    assert any(a.action_type == "error" for a in actions)
    law = list(home.glob("*.pdf"))
    assert any(p.name == HAPPY_YARDS_LAW for p in law)
    assert boom.exists()


def test_litellm_classify_sends_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.classify.router import CLASSIFY_MAX_TOKENS, classify_file
    from harness.extract.pipeline import extract_text

    fixture = PACKAGE_ROOT / "tests" / "fixtures" / "extract" / "sample_invoice.txt"
    monkeypatch.setenv("LOCAL_LITELLM_MASTER_KEY", "sk-test-organizer")
    seen: list[dict] = []

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"prefix":"INV","target_folder":'
                                '"02_Business_Ops/Finance/Invoices_Receivable",'
                                '"description":"SampleInvoice","confidence":0.8}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float):
        seen.append(json)
        assert timeout > 0
        assert timeout <= 120
        return FakeResp()

    monkeypatch.setattr("harness.classify.router.httpx.post", fake_post)
    c = classify_file(
        path=fixture,
        text=extract_text(fixture).text,
        rules=[],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-driver",
        forbid_host_substrings=["api.openai.com"],
    )
    assert seen
    assert seen[0]["max_tokens"] == CLASSIFY_MAX_TOKENS
    assert CLASSIFY_MAX_TOKENS > 0
    assert c.source == "llm"
