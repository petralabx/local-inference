from __future__ import annotations

from pathlib import Path

import pytest

from harness.classify.router import (
    MissingLiteLLMKey,
    classify_file,
    constrain_target_folder,
    correction_rule_rehome,
    human_description,
    match_correction_rules,
)
from harness.config import PACKAGE_ROOT, load_correction_rules
from harness.extract.pipeline import extract_text
from harness.naming import is_compliant, is_organizer_name


FIXTURE = PACKAGE_ROOT / "tests" / "fixtures" / "extract" / "sample_invoice.txt"


def test_extract_text_fixture() -> None:
    result = extract_text(FIXTURE)
    assert "Invoice" in result.text
    assert result.method == "raw"


def test_correction_rule_first() -> None:
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    hit = match_correction_rules("trafilea-brief.pdf", rules)
    assert hit is not None
    assert "Trafilea" in hit["target_folder"]

    c = classify_file(
        path=Path("trafilea-brief.pdf"),
        text="ignored",
        rules=rules,
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        llm_caller=lambda **kw: (_ for _ in ()).throw(AssertionError("llm should not run")),
    )
    assert c.source == "correction_rule"
    assert is_compliant(c.suggested_name)


def test_correction_rule_rehome_only_when_away_from_target(tmp_path: Path) -> None:
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    root = tmp_path / "sp"
    away = root / "00_Inbox" / "trafilea-brief.pdf"
    home = root / "01_Clients_Projects" / "Trafilea" / "trafilea-brief.pdf"
    away.parent.mkdir(parents=True)
    home.parent.mkdir(parents=True)
    away.write_bytes(b"x")
    home.write_bytes(b"x")
    assert correction_rule_rehome(away, root=root, rules=rules) is not None
    assert correction_rule_rehome(home, root=root, rules=rules) is None
    other = root / "00_Inbox" / "random-memo.pdf"
    other.write_bytes(b"y")
    assert correction_rule_rehome(other, root=root, rules=rules) is None


def test_llm_classify_injectable() -> None:
    rules: list = []
    c = classify_file(
        path=FIXTURE,
        text=FIXTURE.read_text(encoding="utf-8"),
        rules=rules,
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com", "api.anthropic.com"],
        llm_caller=lambda **kw: (
            '{"prefix":"INV","target_folder":"02_Business_Ops/Finance/Invoices_Receivable",'
            '"description":"SampleInvoice","confidence":0.8}'
        ),
    )
    assert c.source == "llm"
    assert c.prefix == "INV"
    assert is_compliant(c.suggested_name)


def test_llm_folder_prefix_maps_to_gen() -> None:
    leftover = Path("2026-08-18_01_Atomic Reseller Agreement v01_v01.docx")
    c = classify_file(
        path=leftover,
        text="",
        rules=[],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        organizer_names=True,
        llm_caller=lambda **kw: (
            '{"prefix":"01","target_folder":"01_Clients_Projects",'
            '"description":"Atomic Reseller Agreement v01","confidence":0.9}'
        ),
    )
    assert c.source == "llm"
    assert c.prefix == "GEN"
    assert c.suggested_name == "2026-08-18_GEN_Atomic Reseller Agreement_v01.docx"


def test_correction_rule_peels_stacked_happy_yards_title() -> None:
    rules = load_correction_rules(PACKAGE_ROOT / "config" / "correction_rules.json")
    stacked = Path(
        "2026-08-18_INV_2026-08-18_01_CLIENTS_PROJECTS_"
        "Happy Yards Garden Clean Up Quote_v01_v01.pdf"
    )
    c = classify_file(
        path=stacked,
        text="",
        rules=rules,
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-fast",
        forbid_host_substrings=["api.openai.com"],
        organizer_names=True,
        llm_caller=lambda **kw: (_ for _ in ()).throw(AssertionError("llm should not run")),
    )
    assert c.source == "correction_rule"
    assert c.prefix == "INV"
    assert c.description == "Happy Yards Garden Clean Up Quote"
    assert c.suggested_name == "2026-08-18_INV_Happy Yards Garden Clean Up Quote_v01.pdf"
    assert is_organizer_name(c.suggested_name)


def test_missing_master_key_is_fail_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_LITELLM_MASTER_KEY", raising=False)
    with pytest.raises(MissingLiteLLMKey, match="LOCAL_LITELLM_MASTER_KEY"):
        classify_file(
            path=FIXTURE,
            text="x",
            rules=[],
            litellm_base_url="http://100.103.33.54:4000/v1",
            model="local-driver",
            forbid_host_substrings=["api.openai.com"],
        )


def test_litellm_sends_bearer_and_falls_back_to_coder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCAL_LITELLM_MASTER_KEY", "sk-test-organizer")
    seen: list[str] = []

    class FakeResp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            if "error" in self._payload:
                raise RuntimeError(self._payload["error"])

        def json(self) -> dict:
            return self._payload

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float):
        seen.append(json["model"])
        assert headers.get("Authorization") == "Bearer sk-test-organizer"
        assert url.endswith("/chat/completions")
        if json["model"] == "local-driver":
            return FakeResp({"error": "driver down"})
        return FakeResp(
            {
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
        )

    monkeypatch.setattr("harness.classify.router.httpx.post", fake_post)
    c = classify_file(
        path=FIXTURE,
        text=FIXTURE.read_text(encoding="utf-8"),
        rules=[],
        litellm_base_url="http://100.103.33.54:4000/v1",
        model="local-driver",
        fallback_model="local-coder",
        forbid_host_substrings=["api.openai.com"],
    )
    assert seen == ["local-driver", "local-coder"]
    assert c.source == "llm"
    assert c.prefix == "INV"


def test_invented_folder_and_meta_description_are_constrained() -> None:
    assert constrain_target_folder("Happy Yards") == "00_Inbox/_Unsorted_Imports"
    assert constrain_target_folder("01_Contracts") == "00_Inbox/_Unsorted_Imports"
    assert constrain_target_folder("02_Business_Ops/Finance") == "02_Business_Ops/Finance"
    assert "0701 JA Happy Yards" in human_description(
        "0701 JA Happy Yards.pdf",
        "Binary file with unparsed content, identified by UUID filename.",
        readable=True,
    )


def test_rejects_paid_base_url() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        classify_file(
            path=FIXTURE,
            text="x",
            rules=[],
            litellm_base_url="https://api.openai.com/v1",
            model="gpt-4o",
            forbid_host_substrings=["api.openai.com"],
            llm_caller=lambda **kw: "{}",
        )
