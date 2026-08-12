from __future__ import annotations

import base64
import json
from pathlib import Path

from harness.identity import content_hash
from harness.journal.store import ActionJournal
from harness.mail.graph_client import AttachmentMeta, FakeGraphMailClient
from harness.mail.pipeline import MailIngestPipeline, ensure_mail_folder, ensure_mail_rule


def _load_cassette(path: Path) -> FakeGraphMailClient:
    raw = json.loads(path.read_text(encoding="utf-8"))
    messages: dict[str, list[AttachmentMeta]] = {}
    for mid, atts in (raw.get("messages") or {}).items():
        messages[mid] = [
            AttachmentMeta(
                message_id=mid,
                attachment_id=a["attachment_id"],
                name=a["name"],
                content_bytes=base64.b64decode(a["content_b64"]),
                content_type=a.get("content_type", "application/octet-stream"),
            )
            for a in atts
        ]
    return FakeGraphMailClient(messages=messages)


def test_ensure_folder_and_rule_idempotent() -> None:
    client = FakeGraphMailClient()
    assert ensure_mail_folder(client, "Harness/Inbox") == "Harness/Inbox"
    assert ensure_mail_folder(client, "Harness/Inbox") == "Harness/Inbox"
    assert client.list_mail_folders().count("Harness/Inbox") == 1

    rule = {"displayName": "Harness-Attach-Sort", "sequence": 1}
    r1 = ensure_mail_rule(client, rule)
    r2 = ensure_mail_rule(client, rule)
    assert r1["displayName"] == r2["displayName"]
    assert len(client.list_inbox_rules()) == 1


def test_mail_attachment_save_journaled_and_idempotent(tmp_path: Path) -> None:
    cassette = Path(__file__).parent / "fixtures" / "mail" / "sample_attachments.json"
    client = _load_cassette(cassette)
    journal = ActionJournal(tmp_path / "j.sqlite3")
    run_id = journal.start_run()
    target = tmp_path / "00_Inbox"
    pipe = MailIngestPipeline(client=client, journal=journal, target_dir=target)

    first = pipe.ingest_once(run_id=run_id)
    assert len(first) == 1
    assert first[0].status == "saved"
    assert first[0].saved_paths
    saved = first[0].saved_paths[0]
    assert saved.exists()
    digest = content_hash(saved)
    actions = journal.list_actions(run_id)
    assert any(a.action_type == "mail_attachment_save" for a in actions)

    # Re-seed same message (un-mark) — second ingest skips by content hash
    client.processed.clear()
    client.messages["msg-001"] = [
        AttachmentMeta("msg-001", "att-1", "quote.pdf", b"quote-bytes", "application/pdf")
    ]
    second = pipe.ingest_once(run_id=run_id)
    assert second[0].status == "skipped"
    assert digest in pipe.seen_hashes
    journal.close()
