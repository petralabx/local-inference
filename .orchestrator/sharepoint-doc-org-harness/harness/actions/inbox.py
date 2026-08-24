from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from harness.actions.drain import NOISE_NAMES, is_secret_file
from harness.classify.router import (
    Classification,
    classify_file,
    correction_rule_rehome,
)
from harness.extract.pipeline import extract_text
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move
from harness.ledger.brain import project_document
from harness.ledger.documents import DocumentLedger, DocumentRecord
from harness.naming import (
    ORGANIZER_NAME_RE,
    is_organizer_name,
    next_free_name,
    next_organizer_version,
    next_version_name,
)


@dataclass
class SortResult:
    src: Path
    dest: Path | None
    status: str  # moved | skipped | held
    run_id: str
    detail: str


class InboxSorter:
    """Move-not-copy inbox sorter with processed content-hash manifest."""

    def __init__(
        self,
        *,
        root: Path,
        journal: ActionJournal,
        rules: list[dict[str, Any]],
        litellm_base_url: str,
        model: str,
        forbid_host_substrings: list[str],
        manifest_path: Path,
        llm_caller: Callable[..., str] | None = None,
        classify_fn: Callable[..., Classification] | None = None,
        readable_names: bool = False,
        organizer_names: bool = False,
        fallback_model: str | None = None,
        ledger: DocumentLedger | None = None,
        type_by_prefix: dict[str, str] | None = None,
        project_to_brain: bool = True,
    ) -> None:
        self.root = root
        self.journal = journal
        self.rules = rules
        self.litellm_base_url = litellm_base_url
        self.model = model
        self.forbid_host_substrings = forbid_host_substrings
        self.manifest_path = manifest_path
        self.llm_caller = llm_caller
        self.classify_fn = classify_fn or classify_file
        self.readable_names = readable_names
        self.organizer_names = organizer_names
        self.fallback_model = fallback_model
        self.ledger = ledger
        self.type_by_prefix = type_by_prefix or {}
        self.project_to_brain = project_to_brain
        self._processed = self._load_manifest()

    def _load_manifest(self) -> set[str]:
        if not self.manifest_path.exists():
            return set()
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return set(data.get("sha256") or [])

    def _save_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps({"sha256": sorted(self._processed)}, indent=2),
            encoding="utf-8",
        )

    def process_file(
        self,
        src: Path,
        *,
        run_id: str,
        ignore_manifest: bool = False,
        keep_folder: bool = False,
    ) -> SortResult:
        if not src.is_file():
            return SortResult(src, None, "skipped", run_id, "not a file")
        if src.name.lower() in NOISE_NAMES or src.name.lower() == "_redirect_state.json":
            return SortResult(src, None, "skipped", run_id, "helper or noise")
        if is_secret_file(src):
            return SortResult(src, None, "skipped", run_id, "secret")
        digest = content_hash(src)
        rehome_rule = correction_rule_rehome(src, root=self.root, rules=self.rules)
        in_manifest = digest in self._processed
        in_ledger = self.ledger is not None and self.ledger.get(digest) is not None
        if not ignore_manifest and (in_manifest or in_ledger) and rehome_rule is None:
            if in_ledger and not in_manifest:
                self._processed.add(digest)
                self._save_manifest()
                return SortResult(src, None, "skipped", run_id, "already in ledger")
            return SortResult(src, None, "skipped", run_id, "already processed hash")

        extracted = extract_text(src)
        classification = self.classify_fn(
            path=src,
            text=extracted.text,
            rules=self.rules,
            litellm_base_url=self.litellm_base_url,
            model=self.model,
            forbid_host_substrings=self.forbid_host_substrings,
            llm_caller=self.llm_caller,
            readable_names=self.readable_names,
            organizer_names=self.organizer_names,
            fallback_model=self.fallback_model,
        )
        if (
            not ignore_manifest
            and (in_manifest or in_ledger)
            and classification.source != "correction_rule"
        ):
            if in_ledger and not in_manifest:
                self._processed.add(digest)
                self._save_manifest()
                return SortResult(src, None, "skipped", run_id, "already in ledger")
            return SortResult(src, None, "skipped", run_id, "already processed hash")
        if classification.confidence < 0.5 and classification.source != "correction_rule":
            return SortResult(src, None, "held", run_id, "low confidence")

        # keep_folder is for LLM/heuristic relabel-in-place. A correction-rule
        # home always wins, including the stock relabel job.
        if keep_folder and classification.source != "correction_rule":
            dest_dir = src.parent
        else:
            dest_dir = self.root / classification.target_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        existing = {p.name for p in dest_dir.iterdir()} if dest_dir.exists() else set()
        if self.organizer_names and is_organizer_name(src.name):
            candidate = src.name
            namer = next_organizer_version
        elif self.organizer_names:
            candidate = classification.suggested_name
            namer = next_organizer_version
        elif self.readable_names:
            candidate = classification.suggested_name
            namer = next_free_name
        else:
            candidate = classification.suggested_name
            namer = next_version_name
        name = namer(existing, candidate)
        dest = dest_dir / name
        while dest.exists() and dest.resolve() != src.resolve():
            existing.add(dest.name)
            name = namer(existing, candidate)
            dest = dest_dir / name
        if dest.resolve() != src.resolve():
            apply_move(src, dest)
            action = "move"
        else:
            action = "relabel"
        parsed = ORGANIZER_NAME_RE.match(dest.name)
        version = int(parsed.group("ver")) if parsed else 1
        doc_date = parsed.group("date") if parsed else ""
        try:
            home = dest.relative_to(self.root).parts[0]
        except ValueError:
            home = classification.target_folder.replace("\\", "/").split("/", 1)[0]
        self.journal.record(
            run_id,
            action,
            {
                "from": str(src),
                "to": str(dest),
                "sha256": digest,
                "classification": classification.source,
                "prefix": classification.prefix,
                "title": classification.description,
                "doc_date": doc_date,
                "version": version,
            },
        )
        if self.ledger is not None:
            rec = self.ledger.upsert(
                DocumentRecord(
                    sha256=digest,
                    title=classification.description,
                    prefix=classification.prefix,
                    doc_type=self.type_by_prefix.get(classification.prefix, classification.prefix),
                    doc_date=doc_date,
                    version=version,
                    home=home,
                    current_path=str(dest),
                    source=classification.source,
                )
            )
            if self.project_to_brain:
                project_document(rec)
        self._processed.add(digest)
        self._save_manifest()
        return SortResult(src, dest, "moved", run_id, classification.source)
