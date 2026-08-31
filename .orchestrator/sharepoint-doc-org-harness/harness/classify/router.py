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
    build_entity_topic_title,
    build_name,
    build_organizer_name,
    build_readable_name,
    display_title_part,
    entity_topic_from_name,
    normalize_organizer_prefix,
    parse_organizer_date,
    peel_organizer_title,
    split_entity_topic,
    title_has_entity_and_topic,
    topic_from_blob,
)

MASTER_KEY_ENV = "LOCAL_LITELLM_MASTER_KEY"
UNSORTED_FOLDER = "00_Inbox/_Unsorted_Imports"
# Bound llama.cpp n_predict. Omitting max_tokens maps to n_predict=-1 (unbounded).
CLASSIFY_MAX_TOKENS = 256
CLASSIFY_TIMEOUT_SECONDS = 120.0
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
    entity: str = ""
    topic: str = ""


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
    path: Path | None = None,
    rules: list[dict[str, Any]] | None = None,
    readable_names: bool = False,
    organizer_names: bool = False,
    hold_unknown_entity: bool = True,
) -> Classification:
    blob = f"{filename}\n{text}".lower()
    when = _date_from_name_or_today(filename)
    readable = readable_names or organizer_names
    if "invoice" in blob or re.search(r"\bin\d{6,}", filename.lower()):
        prefix, folder = "INV", "02_Business_Ops/Finance/Invoices_Receivable"
    elif "contract" in blob or "agreement" in blob or "nda" in blob:
        prefix, folder = "CTR", "02_Business_Ops/Legal/Contracts"
    elif "meeting" in blob or "agenda" in blob or "minutes" in blob:
        prefix, folder = "MTG", "04_Admin/Meeting_Notes"
    else:
        prefix, folder = "GEN", "00_Inbox/_Unsorted_Imports"
    desc, entity, topic, hold = _resolve_entity_topic(
        filename=filename,
        text=text,
        path=path,
        rules=rules,
        readable=readable,
    )
    if hold and hold_unknown_entity:
        folder = UNSORTED_FOLDER
    prefix = normalize_organizer_prefix(prefix)
    name = _suggested_name(
        when,
        prefix,
        desc,
        Path(filename).suffix,
        readable_names=readable_names,
        organizer_names=organizer_names,
    )
    return Classification(prefix, folder, desc, 0.45, "heuristic", name, entity, topic)


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
    readable = readable_names or organizer_names
    if hit:
        desc, entity, topic, hold = _resolve_entity_topic(
            filename=path.name,
            text=text,
            path=path,
            rules=rules,
            rule=hit,
            readable=readable,
        )
        prefix = normalize_organizer_prefix(str(hit.get("prefix") or "GEN"))
        folder = UNSORTED_FOLDER if hold else str(hit["target_folder"])
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
            target_folder=folder,
            description=desc,
            confidence=0.9 + 0.02 * int(hit.get("confidence_boost") or 0),
            source="correction_rule",
            suggested_name=name,
            entity=entity,
            topic=topic,
        )

    named_entity, _named_topic = entity_topic_from_name(path.name)
    if named_entity:
        return heuristic_classify(
            path.name,
            text,
            path=path,
            rules=rules,
            readable_names=readable_names,
            organizer_names=organizer_names,
            hold_unknown_entity=True,
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
            desc, entity, topic, hold = _resolve_entity_topic(
                filename=path.name,
                text=text,
                path=path,
                rules=rules,
                llm_entity=str(data.get("entity") or ""),
                llm_topic=str(data.get("topic") or ""),
                llm_description=str(data.get("description") or ""),
                readable=readable,
            )
            if not readable:
                desc = human_description(
                    path.name,
                    str(data.get("description") or ""),
                    readable=False,
                )
            if hold:
                folder = UNSORTED_FOLDER
            conf = float(data.get("confidence") or 0.6)
            name = _suggested_name(
                when,
                prefix,
                desc,
                path.suffix,
                readable_names=readable_names,
                organizer_names=organizer_names,
            )
            return Classification(prefix, folder, desc, conf, "llm", name, entity, topic)
        except MissingLiteLLMKey:
            raise
        except Exception as exc:
            last_error = exc
            continue
    _ = last_error
    return heuristic_classify(
        path.name,
        text,
        path=path,
        rules=rules,
        readable_names=readable_names,
        organizer_names=organizer_names,
    )


def classify_with_order(
    *,
    path: Path,
    text: str,
    rules: list[dict[str, Any]],
    litellm_base_url: str = "",
    model: str = "",
    forbid_host_substrings: list[str] | None = None,
    llm_caller: Callable[..., str] | None = None,
    readable_names: bool = False,
    organizer_names: bool = False,
    fallback_model: str | None = None,
    api_key: str | None = None,
    allow_live_llm: bool = False,
) -> Classification:
    """Leftover-fold order: correction_rule → heuristic → LLM.

    LLM runs only when the heuristic lands on GEN/unsorted and a caller is
    injected or live LLM is explicitly allowed. Dry-run fold planning does
    not require a LiteLLM key.
    """
    hit = match_correction_rules(path.name, rules)
    when = _date_from_name_or_today(path.name)
    readable = readable_names or organizer_names
    if hit:
        desc, entity, topic, hold = _resolve_entity_topic(
            filename=path.name,
            text=text,
            path=path,
            rules=rules,
            rule=hit,
            readable=readable,
        )
        prefix = normalize_organizer_prefix(str(hit.get("prefix") or "GEN"))
        folder = str(hit["target_folder"])
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
            target_folder=folder,
            description=desc,
            confidence=0.9 + 0.02 * int(hit.get("confidence_boost") or 0),
            source="correction_rule",
            suggested_name=name,
            entity=entity,
            topic=topic,
        )

    heur = heuristic_classify(
        path.name,
        text,
        path=path,
        rules=rules,
        readable_names=readable_names,
        organizer_names=organizer_names,
        hold_unknown_entity=False,
    )
    generic = heur.prefix == "GEN" or heur.target_folder == UNSORTED_FOLDER
    if not generic or (llm_caller is None and not allow_live_llm):
        return heur
    try:
        return classify_file(
            path=path,
            text=text,
            rules=rules,
            litellm_base_url=litellm_base_url,
            model=model,
            forbid_host_substrings=forbid_host_substrings or [],
            llm_caller=llm_caller,
            readable_names=readable_names,
            organizer_names=organizer_names,
            fallback_model=fallback_model,
            api_key=api_key,
        )
    except MissingLiteLLMKey:
        return heur


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
        "Return ONLY JSON with keys prefix, target_folder, entity, topic, confidence. "
        "target_folder MUST start with one of: 00_Inbox, 01_Clients_Projects, "
        "02_Business_Ops, 03_Marketing_Creative, 04_Admin, 05_Personal, 06_Reference. "
        "entity is the customer, vendor, PLX department, government agency, or person "
        "the document is about. topic is what the document is in words "
        "(invoice, quote, contract, notice of assessment, cost analysis, …). "
        "The organizer will set the filename title to '{entity} {topic}'. "
        "If you cannot name the entity from the filename, path, or text, set entity to "
        "an empty string and target_folder to 00_Inbox/_Unsorted_Imports. "
        "Do not invent a party. Do not guess a fake customer. "
        "If unsure use 00_Inbox/_Unsorted_Imports. "
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
            "max_tokens": CLASSIFY_MAX_TOKENS,
        },
        timeout=CLASSIFY_TIMEOUT_SECONDS,
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
        stem = peel_organizer_title(stem) or stem
        stem = re.sub(r"[\\/<>:\"|?*]+", " ", stem)
        stem = re.sub(r"\s+", " ", stem).strip()
        return stem[:80] or "Untitled"
    stem = re.sub(r"[^A-Za-z0-9]+", "", stem)
    return stem[:48] or "Untitled"


def _date_from_name_or_today(filename: str) -> date:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        parsed = parse_organizer_date(m.group(1))
        if parsed is not None:
            return parsed
    return datetime.now().date()


def entity_from_correction_rule(rule: dict[str, Any], blob: str) -> str:
    """Optional rule party/entity, else the matching keyword, else the folder."""
    explicit = str(rule.get("party") or rule.get("entity") or "").strip()
    if explicit:
        return explicit
    keywords = sorted((str(k) for k in (rule.get("keywords") or [])), key=len, reverse=True)
    low = blob.lower()
    for kw in keywords:
        needle = kw.lower()
        idx = low.find(needle)
        if idx >= 0:
            sliced = blob[idx : idx + len(kw)].strip()
            return display_title_part(sliced or kw)
    if keywords:
        return display_title_part(str(keywords[0]))
    folder = str(rule.get("target_folder") or "").replace("\\", "/").strip("/")
    parts = [p for p in folder.split("/") if p and p not in ALLOWED_HOMES]
    if parts:
        return display_title_part(parts[0].replace("_", " "))
    return ""


def entity_from_client_folder(path: Path) -> str:
    """01_Clients_Projects/<Client>/… only. Other homes are not a party."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part != "01_Clients_Projects" or i + 1 >= len(parts):
            continue
        child = parts[i + 1]
        if child == path.name or child.startswith(".") or child.startswith("_"):
            return ""
        return display_title_part(child.replace("_", " "))
    return ""


def _looks_like_organizer_title(text: str) -> bool:
    return title_has_entity_and_topic(text)


def _resolve_entity_topic(
    *,
    filename: str,
    text: str = "",
    path: Path | None = None,
    rules: list[dict[str, Any]] | None = None,
    rule: dict[str, Any] | None = None,
    llm_entity: str = "",
    llm_topic: str = "",
    llm_description: str = "",
    readable: bool,
) -> tuple[str, str, str, bool]:
    """Return description, entity, topic, hold_unsorted.

    Hold when the entity cannot be named. Never invent a party.
    """
    peeled = _desc(filename, readable=readable)
    if not readable:
        return peeled, "", "", False

    named_entity, named_topic = entity_topic_from_name(filename)
    if named_entity and rule is None:
        desc = build_entity_topic_title(named_entity, named_topic) or peeled
        return desc, named_entity, named_topic, False

    blob = " ".join(
        part
        for part in (filename, peeled, text[:800], str(path) if path else "")
        if part
    )
    entity = display_title_part(llm_entity)
    topic = display_title_part(llm_topic)
    if rule is not None:
        entity = entity or entity_from_correction_rule(rule, blob)
    if not entity and rules:
        hit = match_correction_rules(blob, rules)
        if hit is not None:
            entity = entity_from_correction_rule(hit, blob)
    if not entity:
        split_e, split_t = split_entity_topic(peeled)
        entity = entity or split_e
        topic = topic or split_t
    if not entity and path is not None:
        entity = entity_from_client_folder(path)
    if not entity and named_entity:
        entity = named_entity
        topic = topic or named_topic
    if not topic:
        _, split_t = split_entity_topic(llm_description or peeled)
        topic = topic or split_t
    if not topic:
        topic = topic_from_blob(filename, text, peeled, llm_description)

    if _looks_like_organizer_title(peeled) and (
        not entity or entity.lower() in peeled.lower()
    ):
        if not entity:
            entity, topic = split_entity_topic(peeled)
        elif not topic:
            _, topic = split_entity_topic(peeled)
        built = build_entity_topic_title(entity, topic)
        desc = peeled if " " in peeled and title_has_entity_and_topic(peeled) else (built or peeled)
        return desc, entity, topic, False

    if not entity:
        return peeled, "", topic, True
    if not topic:
        spaced = re.sub(r"[\s_-]+", " ", peeled).strip()
        residue = spaced
        if spaced.lower().startswith(entity.lower()):
            residue = spaced[len(entity) :].strip()
        if residue and residue.lower() != entity.lower():
            topic = display_title_part(residue)
        elif llm_description and not _META_DESC.search(llm_description):
            topic = display_title_part(llm_description)
    if not topic:
        return peeled, entity, "", True
    desc = build_entity_topic_title(entity, topic)
    if not desc:
        return peeled, entity, topic, True
    return desc, entity, topic, False
