from __future__ import annotations

from pathlib import Path

import pytest

from harness.classify.router import (
    MissingLiteLLMKey,
    classify_file,
    match_correction_rules,
)
from harness.config import PACKAGE_ROOT, load_correction_rules
from harness.extract.pipeline import extract_text
from harness.naming import is_compliant


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
