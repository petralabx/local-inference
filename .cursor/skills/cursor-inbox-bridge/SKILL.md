---
name: cursor-inbox-bridge
description: Sync and inspect the operator's Cursor Inbox / OneDrive review artifacts. Use when the user mentions OneDrive, CursorInbox, local downloads, uploaded zips, screenshots, or files to review from outside the current repo.
---

# Cursor Inbox Bridge

Use when the user mentions OneDrive, CursorInbox, local downloads, uploaded zips,
screenshots, or files to review from outside the current repo.

## Workflow

1. Run `/home/vinnysachet/bin/sync-cursor-inbox-onedrive.sh`.
2. Inspect `/home/vinnysachet/cursor-inbox/onedrive`.
3. Use synced files directly; do not ask Vince to re-upload files that are already
   in CursorInbox.

## Safety

- The sync is copy-only and never deletes local review artifacts.
- For diagnostics, run `/home/vinnysachet/bin/sync-cursor-inbox-onedrive.sh --self-check`.
