from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from harness.actions.drain import NOISE_NAMES, is_secret_file
from harness.classify.router import Classification, classify_file
from harness.extract.pipeline import extract_text
from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move
from harness.naming import next_free_name, next_version_name


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
        fallback_model: str | None = None,
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
        self.fallback_model = fallback_model
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

    def process_file(self, src: Path, *, run_id: str) -> SortResult:
        if not src.is_file():
            return SortResult(src, None, "skipped", run_id, "not a file")
        if src.name.lower() in NOISE_NAMES or src.name.lower() == "_redirect_state.json":
            return SortResult(src, None, "skipped", run_id, "helper or noise")
        if is_secret_file(src):
            return SortResult(src, None, "skipped", run_id, "secret")
        digest = content_hash(src)
        if digest in self._processed:
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
            fallback_model=self.fallback_model,
        )
        if classification.confidence < 0.5 and classification.source != "correction_rule":
            return SortResult(src, None, "held", run_id, "low confidence")

        dest_dir = self.root / classification.target_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        existing = {p.name for p in dest_dir.iterdir()} if dest_dir.exists() else set()
        namer = next_free_name if self.readable_names else next_version_name
        name = namer(existing, classification.suggested_name)
        dest = dest_dir / name
        while dest.exists():
            existing.add(dest.name)
            name = namer(existing, classification.suggested_name)
            dest = dest_dir / name
        apply_move(src, dest)
        self.journal.record(
            run_id,
            "move",
            {
                "from": str(src),
                "to": str(dest),
                "sha256": digest,
                "classification": classification.source,
            },
        )
        self._processed.add(digest)
        self._save_manifest()
        return SortResult(src, dest, "moved", run_id, classification.source)
