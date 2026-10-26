---
name: resume-workstream
description: Load this branch's workstream note from docs/workstreams/, check it against the repo, and summarise where the work stands and what to do next. Use at the start of a session that continues earlier work.
disable-model-invocation: true
---

# /resume-workstream

Pick up a workstream where the last session left it. (The built-in `/resume` reopens a past
conversation; this command reloads the work from the repo instead.)

1. Run `node scripts/workstream-note.mjs path`. If it prints nothing, list the active
   workstreams from `docs/workstreams/README.md` and ask which one this session continues.
2. Read the note and its index row, including the workstreams it depends on.
3. Check the note against the repo before you trust it:
   - `git log` on this branch since the note's Last updated date.
   - The open PRs for the branch, their CI and review state.
   - The Mission Control tasks the note names.
   - The SharePoint handoff it links, if any. SharePoint wins when the two disagree.
4. Tell the user, briefly: the goal, the status, what changed since the note was written, the
   next steps, the open questions and the blockers. Name anything in the note that is now wrong.
5. Propose the next step and wait for the go-ahead before you edit. Keep to the workstream's
   scope, and flag any edit outside it before you make it.
6. If the note was wrong or stale, fix it with `/handoff` once the work moves.
