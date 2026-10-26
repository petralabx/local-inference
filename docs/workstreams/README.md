# Workstreams

Sessions and personal configs are disposable. Anything the next session or a teammate needs
lives here, in files that travel with the code. Each workstream has one handoff note, and this
page indexes the active ones. Git history is the audit trail.

## The protocol

1. One workstream per branch and worktree. Flag any edit outside your workstream's scope
   before you make it.
2. At session start, read your workstream's note. The index below maps branches to notes.
3. Before you end a session, and after any significant decision, update the note in the same
   branch as the work.
4. Change the index row only when a workstream opens, closes or changes status. Day-to-day
   detail goes in the note, so the index rarely conflicts.
5. SharePoint `Agent Handoffs/` stays the system of record for durable handoffs. The note is the
   agents' working copy beside the code. When the two disagree, SharePoint wins: fix the note.

A one-PR change does not need a workstream. Start one when the work will span more than one
PR, session or agent.

## Notes

- One file per workstream: `docs/workstreams/<slug>.md`, where the slug is lowercase
  kebab-case (`ci-redesign`, `grid-cost-rules`).
- Copy [`_template.md`](_template.md). Keep every section, in order, even when it says "None".
- Replace stale text instead of appending a diary. The note says where things stand now; git
  history says how they got there.
- A workstream whose note lives in another repository links there from its index row.

## Branches and worktrees

- Where you choose the branch name, use `<lane>/<slug>` or `<lane>/<slug>-<n>`
  (`claude/ci-redesign-2`, `cursor/grid-cost-rules`). The hooks match those to the note.
- Where the tool names the branch (Claude Code on the web), list the branch in the index row.
- Put local worktrees under `.worktrees/<slug>/` (Claude Code uses `.claude/worktrees/`). Both
  are gitignored.

## Tools

- **Claude Code:** `/handoff` updates the note and `/resume-workstream` loads it. Repo hooks
  print the note at session start (and again after compaction) and ask once for an update when
  the note is older than the branch's latest change.
- **Cursor:** the same two commands are in `.cursor/commands/`. The rule
  `.cursor/rules/workstreams.mdc` applies the note format while you edit this folder.
- **Codex, Grok and other agents:** the protocol is in `AGENTS.md`. Ask the agent to follow it
  and to update the note before it stops.
- **Check:** `node scripts/workstream-note.mjs check` confirms the index and the notes agree.

## Index

Status is one of `active`, `blocked`, `paused` or `done`. Prune `done` rows and their notes
after 30 days; git history keeps them.

| Workstream | Owner | Branches | Status | Depends on | MC tasks |
|---|---|---|---|---|---|
