from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AttachmentMeta:
    message_id: str
    attachment_id: str
    name: str
    content_bytes: bytes
    content_type: str = "application/octet-stream"


class GraphMailClient(Protocol):
    """Delegated Graph mail surface (live SDK or test fake)."""

    def list_mail_folders(self) -> list[str]: ...

    def create_mail_folder(self, name: str) -> str: ...

    def list_inbox_rules(self) -> list[dict]: ...

    def create_inbox_rule(self, rule: dict) -> dict: ...

    def list_messages_with_attachments(self, folder: str = "Inbox") -> list[str]: ...

    def list_attachments(self, message_id: str) -> list[AttachmentMeta]: ...

    def mark_processed(self, message_id: str, category: str = "HarnessProcessed") -> None: ...


@dataclass
class FakeGraphMailClient:
    """In-memory Graph stand-in for cassette-style tests (no live mailbox)."""

    folders: list[str] = field(default_factory=lambda: ["Inbox"])
    rules: list[dict] = field(default_factory=list)
    messages: dict[str, list[AttachmentMeta]] = field(default_factory=dict)
    processed: set[str] = field(default_factory=set)

    def list_mail_folders(self) -> list[str]:
        return list(self.folders)

    def create_mail_folder(self, name: str) -> str:
        if name not in self.folders:
            self.folders.append(name)
        return name

    def list_inbox_rules(self) -> list[dict]:
        return list(self.rules)

    def create_inbox_rule(self, rule: dict) -> dict:
        existing = {r.get("displayName") for r in self.rules}
        if rule.get("displayName") in existing:
            return next(r for r in self.rules if r.get("displayName") == rule.get("displayName"))
        self.rules.append(dict(rule))
        return dict(rule)

    def list_messages_with_attachments(self, folder: str = "Inbox") -> list[str]:
        return [mid for mid in self.messages if mid not in self.processed]

    def list_attachments(self, message_id: str) -> list[AttachmentMeta]:
        return list(self.messages.get(message_id, []))

    def mark_processed(self, message_id: str, category: str = "HarnessProcessed") -> None:
        self.processed.add(message_id)
