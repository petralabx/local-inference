from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from harness.naming import build_name


@dataclass
class Classification:
    prefix: str
    target_folder: str
    description: str
    confidence: float
    source: str  # correction_rule | llm | heuristic
    suggested_name: str


def match_correction_rules(filename: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    low = filename.lower()
    best = None
    best_boost = -1
    for rule in rules:
        kws = rule.get("keywords") or []
        if any(str(k).lower() in low for k in kws):
            boost = int(rule.get("confidence_boost") or 0)
            if boost > best_boost:
                best = rule
                best_boost = boost
    return best


def heuristic_classify(filename: str, text: str) -> Classification:
    blob = f"{filename}\n{text}".lower()
    when = _date_from_name_or_today(filename)
    if "invoice" in blob or re.search(r"\bin\d{6,}", filename.lower()):
        prefix, folder, desc = "INV", "02_Business_Ops/Finance/Invoices_Receivable", _desc(filename)
    elif "contract" in blob or "agreement" in blob or "nda" in blob:
        prefix, folder, desc = "CTR", "02_Business_Ops/Legal/Contracts", _desc(filename)
    elif "meeting" in blob or "agenda" in blob or "minutes" in blob:
        prefix, folder, desc = "MTG", "04_Admin/Meeting_Notes", _desc(filename)
    else:
        prefix, folder, desc = "GEN", "00_Inbox/_Unsorted_Imports", _desc(filename)
    name = build_name(when=when, prefix=prefix, description=desc, ext=Path(filename).suffix)
    return Classification(prefix, folder, desc, 0.45, "heuristic", name)


def classify_file(
    *,
    path: Path,
    text: str,
    rules: list[dict[str, Any]],
    litellm_base_url: str,
    model: str,
    forbid_host_substrings: list[str],
    llm_caller: Callable[..., str] | None = None,
) -> Classification:
    for needle in forbid_host_substrings:
        if needle.lower() in litellm_base_url.lower():
            raise ValueError(f"Paid/cloud inference host forbidden: {needle}")

    hit = match_correction_rules(path.name, rules)
    when = _date_from_name_or_today(path.name)
    if hit:
        desc = _desc(path.name)
        name = build_name(
            when=when,
            prefix=str(hit.get("prefix") or "GEN"),
            description=desc,
            ext=path.suffix,
        )
        return Classification(
            prefix=str(hit.get("prefix") or "GEN"),
            target_folder=str(hit["target_folder"]),
            description=desc,
            confidence=0.9 + 0.02 * int(hit.get("confidence_boost") or 0),
            source="correction_rule",
            suggested_name=name,
        )

    # LLM path (injectable for tests)
    caller = llm_caller or (lambda **kw: _litellm_classify(**kw))
    try:
        raw = caller(
            base_url=litellm_base_url,
            model=model,
            filename=path.name,
            text=text[:4000],
        )
        data = json.loads(raw)
        prefix = str(data.get("prefix") or "GEN")
        folder = str(data.get("target_folder") or "00_Inbox/_Unsorted_Imports")
        desc = str(data.get("description") or _desc(path.name))
        conf = float(data.get("confidence") or 0.6)
        name = build_name(when=when, prefix=prefix, description=desc, ext=path.suffix)
        return Classification(prefix, folder, desc, conf, "llm", name)
    except Exception:
        return heuristic_classify(path.name, text)


def _litellm_classify(*, base_url: str, model: str, filename: str, text: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    prompt = (
        "Classify this document for SharePoint filing. "
        "Return ONLY JSON with keys prefix, target_folder, description, confidence. "
        f"filename={filename}\ntext=\n{text}"
    )
    resp = httpx.post(
        url,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    # Strip fences if present
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    return content


def _desc(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[^A-Za-z0-9]+", "", stem)
    return stem[:48] or "Untitled"


def _date_from_name_or_today(filename: str) -> date:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return date.fromisoformat(m.group(1))
    return datetime.now().date()
