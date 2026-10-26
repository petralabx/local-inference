# Resume workstream

Pick up this branch's workstream where the last session left it.

1. Run `node scripts/workstream-note.mjs path`. If it prints nothing, list the active workstreams
   from `docs/workstreams/README.md` and ask which one this session continues.
2. Read the note and its index row, including the workstreams it depends on.
3. Check it against the repo: `git log` since Last updated, the branch's open PRs and CI, the
   Mission Control tasks it names, and its SharePoint handoff (SharePoint wins on conflict).
4. Summarise the goal, status, what changed since the note, next steps, open questions and
   blockers. Name anything in the note that is now wrong.
5. Propose the next step and wait for the go-ahead. Flag any edit outside the workstream's scope.
