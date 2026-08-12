from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.mail.graph_client import GraphMailClient


def ensure_mail_folder(client: GraphMailClient, name: str) -> str:
    """Idempotent folder ensure."""
    if name in client.list_mail_folders():
        return name
    return client.create_mail_folder(name)


def ensure_mail_rule(client: GraphMailClient, rule: dict) -> dict:
    """Idempotent inbox rule ensure (match by displayName)."""
    name = rule.get("displayName")
    for existing in client.list_inbox_rules():
        if existing.get("displayName") == name:
            return existing
    return client.create_inbox_rule(rule)


@dataclass
class IngestResult:
    message_id: str
    saved_paths: list[Path]
    status: str  # saved | skipped


class MailIngestPipeline:
    """Save Graph attachments into SharePoint inbox (or target) with journal + hash idempotency."""

    def __init__(
        self,
        *,
        client: GraphMailClient,
        journal: ActionJournal,
        target_dir: Path,
        seen_hashes: set[str] | None = None,
    ) -> None:
        self.client = client
        self.journal = journal
        self.target_dir = target_dir
        self.seen_hashes = seen_hashes if seen_hashes is not None else set()

    def ingest_once(self, *, run_id: str, folder: str = "Inbox") -> list[IngestResult]:
        self.target_dir.mkdir(parents=True, exist_ok=True)
        results: list[IngestResult] = []
        for mid in self.client.list_messages_with_attachments(folder):
            saved: list[Path] = []
            for att in self.client.list_attachments(mid):
                # Write to temp name then hash for idempotency
                dest = self.target_dir / att.name
                if dest.exists():
                    dest = self.target_dir / f"{Path(att.name).stem}__{mid[:8]}{Path(att.name).suffix}"
                dest.write_bytes(att.content_bytes)
                digest = content_hash(dest)
                if digest in self.seen_hashes:
                    dest.unlink(missing_ok=True)
                    continue
                self.seen_hashes.add(digest)
                self.journal.record(
                    run_id,
                    "mail_attachment_save",
                    {
                        "message_id": mid,
                        "attachment_id": att.attachment_id,
                        "path": str(dest),
                        "sha256": digest,
                        "name": att.name,
                    },
                )
                saved.append(dest)
            self.client.mark_processed(mid)
            results.append(
                IngestResult(mid, saved, "saved" if saved else "skipped"),
            )
        return results
