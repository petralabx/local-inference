from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from harness.naming import (
    build_name,
    build_organizer_name,
    build_readable_name,
    normalize_organizer_prefix,
)

MASTER_KEY_ENV = "LOCAL_LITELLM_MASTER_KEY"
UNSORTED_FOLDER = "00_Inbox/_Unsorted_Imports"
ALLOWED_HOMES = {
    "00_Inbox",
    "01_Clients_Projects",
    "02_Business_Ops",
    "03_Marketing_Creative",
    "04_Admin",
    "05_Personal",
    "06_Reference",
}
_META_DESC = re.compile(
    r"unparsed|identified by|awaiting further|binary file|uuid filename|no extracted text",
    re.I,
)


class MissingLiteLLMKey(RuntimeError):
    """Raised when classify would call LiteLLM without a master key."""


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


def correction_rule_rehome(
    path: Path,
    *,
    root: Path,
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the matching rule when path is not already in that rule's folder.

    Filename-only. Does not classify via LLM, so hashed leftovers can be
    rehomed without opening the rest of the library.
    """
    hit = match_correction_rules(path.name, rules)
    if hit is None:
        return None
    target = root / str(hit.get("target_folder") or "").replace("\\", "/")
    try:
        if path.parent.resolve() == target.resolve():
            return None
    except OSError:
        return hit
    return hit


def heuristic_classify(
    filename: str,
    text: str,
    *,
    readable_names: bool = False,
    organizer_names: bool = False,
) -> Classification:
    blob = f"{filename}\n{text}".lower()
    when = _date_from_name_or_today(filename)
    desc = _desc(filename, readable=readable_names or organizer_names)
    if "invoice" in blob or re.search(r"\bin\d{6,}", filename.lower()):
        prefix, folder = "INV", "02_Business_Ops/Finance/Invoices_Receivable"
    elif "contract" in blob or "agreement" in blob or "nda" in blob:
        prefix, folder = "CTR", "02_Business_Ops/Legal/Contracts"
    elif "meeting" in blob or "agenda" in blob or "minutes" in blob:
        prefix, folder = "MTG", "04_Admin/Meeting_Notes"
    else:
        prefix, folder = "GEN", "00_Inbox/_Unsorted_Imports"
    prefix = normalize_organizer_prefix(prefix)
    name = _suggested_name(
        when,
        prefix,
        desc,
        Path(filename).suffix,
        readable_names=readable_names,
        organizer_names=organizer_names,
    )
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
    readable_names: bool = False,
    organizer_names: bool = False,
    fallback_model: str | None = None,
    api_key: str | None = None,
) -> Classification:
    for needle in forbid_host_substrings:
        if needle.lower() in litellm_base_url.lower():
            raise ValueError(f"Paid/cloud inference host forbidden: {needle}")

    hit = match_correction_rules(path.name, rules)
    when = _date_from_name_or_today(path.name)
    if hit:
        desc = _desc(path.name, readable=readable_names or organizer_names)
        prefix = normalize_organizer_prefix(str(hit.get("prefix") or "GEN"))
        name = _suggested_name(
            when,
            prefix,
            desc,
            path.suffix,
            readable_names=readable_names,
            organizer_names=organizer_names,
        )
        return Classification(
            prefix=prefix,
            target_folder=str(hit["target_folder"]),
            description=desc,
            confidence=0.9 + 0.02 * int(hit.get("confidence_boost") or 0),
            source="correction_rule",
            suggested_name=name,
        )

    # LLM path (injectable for tests). A missing master key is fail-visible;
    # HTTP/parse failures still fall back to the filename heuristic.
    key = api_key if api_key is not None else os.environ.get(MASTER_KEY_ENV, "")
    if llm_caller is None and not key:
        raise MissingLiteLLMKey(
            f"{MASTER_KEY_ENV} is required for Organizer classify; "
            "do not call LiteLLM without a Bearer token."
        )

    caller = llm_caller or (lambda **kw: _litellm_classify(**kw))
    models = [model]
    if fallback_model and fallback_model != model:
        models.append(fallback_model)
    last_error: Exception | None = None
    for candidate in models:
        try:
            raw = caller(
                base_url=litellm_base_url,
                model=candidate,
                filename=path.name,
                text=text[:4000],
                api_key=key,
            )
            data = json.loads(raw)
            prefix = normalize_organizer_prefix(str(data.get("prefix") or "GEN"))
            folder = constrain_target_folder(str(data.get("target_folder") or UNSORTED_FOLDER))
            desc = human_description(
                path.name,
                str(data.get("description") or ""),
                readable=readable_names or organizer_names,
            )
            conf = float(data.get("confidence") or 0.6)
            name = _suggested_name(
                when,
                prefix,
                desc,
                path.suffix,
                readable_names=readable_names,
                organizer_names=organizer_names,
            )
            return Classification(prefix, folder, desc, conf, "llm", name)
        except MissingLiteLLMKey:
            raise
        except Exception as exc:
            last_error = exc
            continue
    _ = last_error
    return heuristic_classify(
        path.name,
        text,
        readable_names=readable_names,
        organizer_names=organizer_names,
    )


def _litellm_classify(
    *,
    base_url: str,
    model: str,
    filename: str,
    text: str,
    api_key: str = "",
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    prompt = (
        "Classify this document for VincePersonal SharePoint filing. "
        "Return ONLY JSON with keys prefix, target_folder, description, confidence. "
        "target_folder MUST start with one of: 00_Inbox, 01_Clients_Projects, "
        "02_Business_Ops, 03_Marketing_Creative, 04_Admin, 05_Personal, 06_Reference. "
        "If unsure use 00_Inbox/_Unsorted_Imports. "
        "description is a short human title, not a sentence about the file being unparsed. "
        f"filename={filename}\ntext=\n{text}"
    )
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = httpx.post(
        url,
        headers=headers,
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


def constrain_target_folder(folder: str) -> str:
    cleaned = folder.replace("\\", "/").strip().lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        return UNSORTED_FOLDER
    top = cleaned.split("/", 1)[0]
    if top in ALLOWED_HOMES:
        return cleaned
    return UNSORTED_FOLDER


def human_description(filename: str, desc: str, *, readable: bool) -> str:
    text = (desc or "").strip()
    if not text or len(text) > 80 or _META_DESC.search(text):
        return _desc(filename, readable=readable)
    return text


def _suggested_name(
    when: date,
    prefix: str,
    desc: str,
    ext: str,
    *,
    readable_names: bool,
    organizer_names: bool = False,
) -> str:
    if organizer_names:
        return build_organizer_name(when=when, prefix=prefix, title=desc, ext=ext)
    if readable_names:
        return build_readable_name(description=desc, ext=ext)
    return build_name(when=when, prefix=prefix, description=desc, ext=ext)


def _desc(filename: str, *, readable: bool = False) -> str:
    stem = Path(filename).stem
    if readable:
        stem = re.sub(r"[\\/<>:\"|?*]+", " ", stem)
        stem = re.sub(r"\s+", " ", stem).strip()
        return stem[:80] or "Untitled"
    stem = re.sub(r"[^A-Za-z0-9]+", "", stem)
    return stem[:48] or "Untitled"


def _date_from_name_or_today(filename: str) -> date:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return date.fromisoformat(m.group(1))
    return datetime.now().date()
