# Handoff

Update this branch's workstream note in `docs/workstreams/` so the next session or teammate can
pick it up.

1. Run `node scripts/workstream-note.mjs path` to find the note. If it prints nothing and this
   work spans more than one PR, session or agent, copy `docs/workstreams/_template.md` to
   `docs/workstreams/<slug>.md` and add an index row in `docs/workstreams/README.md`.
2. Rewrite every section from this session: Status (with date), Done (PR links), Next steps,
   Decisions and why (dated), Open questions, Files / areas touched, How to run the tests,
   Blockers or dependencies on other workstreams, Last updated (YYYY-MM-DD). Replace stale text.
3. Update the index row only if the status changed or the workstream opened or closed.
4. Run `node scripts/workstream-note.mjs check`, then commit the note with the work.
5. SharePoint `Agent Handoffs/` is the system of record for durable handoffs; file there too when
   the workstream closes or changes hands.
