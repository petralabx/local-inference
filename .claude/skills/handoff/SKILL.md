---
name: handoff
description: Update this workstream's handoff note in docs/workstreams/ so the next session or teammate can pick it up. Use before you end a session, after a significant decision, or when the Stop hook says the note is stale.
disable-model-invocation: true
---

# /handoff

Bring this branch's workstream note up to date. The note is the agents' working copy; SharePoint
`Agent Handoffs/` stays the system of record for durable handoffs.

1. Run `node scripts/workstream-note.mjs path`.
   - It prints a note path: open that note.
   - It prints a URL: the note lives in another repository. Update it there, or tell the user.
   - It prints nothing: ask whether this work is a workstream (it spans more than one PR, session
     or agent). If it is, copy `docs/workstreams/_template.md` to `docs/workstreams/<slug>.md`
     (lowercase kebab-case) and add a row to the index in `docs/workstreams/README.md`. If it is a
     one-PR change, say so and stop.
2. Rewrite each section from what this session did and decided. Keep every section, in template
   order. Replace stale text instead of appending; git history keeps the old version.
   - **Status**: `active`, `blocked`, `paused` or `done`, with today's date and one line.
   - **Done**: what landed, with PR links. **Next steps**: numbered, the next one first.
   - **Decisions and why**: dated, with who decided. **Open questions**: with who can answer.
   - **Files / areas touched**, **How to run the tests**, **Blockers or dependencies on other
     workstreams**: as they are now.
   - **Last updated**: today's date (YYYY-MM-DD, ET) and this session or agent.
3. If the status changed, or the workstream opened or closed, update its index row. Otherwise
   leave the index alone.
4. Run `node scripts/workstream-note.mjs check` and fix what it reports.
5. Commit the note on this branch with the work it describes, using the repo's commit rules
   (Mission Control trailers included).
6. If this hands the workstream to another team or agent family, or closes it, also file the
   handoff in SharePoint `Agent Handoffs/` as the repo's rules describe. SharePoint wins when
   the two disagree.

Report the note path and the three most important next steps to the user.
