# P6 — Outlook and attachments

- FakeGraphMailClient + cassette fixture (no live mailbox).
- Idempotent folder/rule ensure; attachment save journaled with hash skip.
- Acceptance: `python -m pytest -q -k test_p6_`
