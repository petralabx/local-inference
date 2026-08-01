# Project Orchestrator — Worked Example

A full end-to-end run of a small project: **"Add CSV export to the reports page."**
Generic on purpose — the flow is identical in any repo. Read [SKILL.md](SKILL.md) first.

## Stage 0 — Calibrate
`pre-plan-recalibrator` surfaces: must export the *currently filtered* rows; CSV must
match the on-screen columns; no new dependency; success = a user can download a valid
CSV from the reports page. Non-goal: XLSX, scheduled exports.

## Stage 1 — Spec
`scripts/new-project.sh csv-export` scaffolds `.orchestrator/csv-export/SPEC.md`.
Filled in (abridged):

```markdown
---
project: csv-export
status: draft
budget: { max_parallel_phases: 2, max_attempts_per_phase: 3, time_budget_min: 0 }
---
# Add CSV export to the reports page
## Success Criteria
- [ ] GET /api/reports/export returns text/csv for the active filter
- [ ] Reports page has an Export button that downloads the CSV
- [ ] Lint + typecheck + unit tests pass
## Phases
### P1 — export endpoint
- deliverables: serialize filtered rows to CSV behind an API route
- depends_on: []
- owns: ["src/server/reports/**", "src/lib/csv/**"]
- forbidden: ["src/components/**"]
- acceptance: `npm test -- reports-export`
- role: builder
- competitive: false
### P2 — export button (UI)
- deliverables: button on reports page that calls the endpoint and downloads
- depends_on: [P1]
- owns: ["src/components/reports/**"]
- forbidden: ["src/server/**"]
- acceptance: `npm run typecheck && npm test -- reports-ui`
- role: builder
### P3 — docs + cleanup
- deliverables: README usage note; remove the dead stub exporter
- depends_on: [P1, P2]
- owns: ["docs/**", "src/lib/csv/**"]
- forbidden: []
- acceptance: `npm run lint`
- role: mechanical
## Worktree Plan
- base: proj/csv-export · phases proj/csv-export/phase-<k> · integration proj/csv-export/integration
```

Validate:
```bash
scripts/spec-validate.sh .orchestrator/csv-export/SPEC.md
# OK: 3 phases, ids unique, deps resolve, DAG acyclic, all acceptance commands present
```

## Stage 2 — Approval gate
No override file, so resolve models at runtime by role criteria and present:

```
Proposed model_plan (confirm or edit):
  planner    -> <best reasoning model available now>
  builder    -> <best balanced coding model available now>
  mechanical -> <fastest low-cost model available now>
  critic     -> <capable model from a different family than builder>
Phases: P1, P2(after P1), P3(after P1,P2). One integration PR. Approve? [y/edit]
```

User approves → set `status: approved`, write `model_plan`, `approved_by`,
`approved_at`. **Execution starts only now.**

## Stage 3 — Execute
DAG readiness: P1 ready; P2 waits on P1; P3 waits on P1+P2. With
`max_parallel_phases: 2`, P1 runs first (nothing else is ready).

```
Task subagent_type=best-of-n-runner  model=<model_plan.builder>  run_in_background=true
  description="exec P1 csv-export"
  prompt="Implement phase P1 on branch proj/csv-export/phase-1-export-endpoint.
          Scope (owns): src/server/reports/**, src/lib/csv/**. only WRITE within owns.
          Forbidden (auto-reject if touched): src/components/**.
          Deliverables: serialize filtered rows to CSV behind an API route.
          Required artifacts at .orchestrator/csv-export/P1/: patch.diff, NOTES.md, commands.log.
          Acceptance you must make pass locally: npm test -- reports-export.
          Produce the diff/commit on your branch. DO NOT merge.
          Stop after 3 failed attempts and write BLOCKER.md."
```

P1 acceptance (orchestrator-run):
```bash
git -C <p1-worktree> diff --name-only proj/csv-export... > /tmp/changed.txt
scripts/scope-check.sh "src/server/reports/** src/lib/csv/**" "src/components/**" $(cat /tmp/changed.txt)
( cd <p1-worktree> && npm test -- reports-export )   # exit 0 -> P1 complete
```

P1 complete → P2 becomes ready and runs (same spawn pattern, `model_plan.builder`,
its own scope). When P2 completes, P3 (mechanical) runs.

### Scope drift caught
P2's runner edits `src/server/reports/route.ts` "to add a header". `scope-check.sh`
sees a changed file outside P2's `owns` (and inside its `forbidden src/server/**`),
exits non-zero → **scope drift**, phase rejected, retried with a sharper scope
reminder. The server change, if actually needed, belongs in a spec revision to P1.

## Stage 4 — Integrate
```bash
git checkout -b proj/csv-export/integration proj/csv-export
git merge --no-ff proj/csv-export/phase-1-export-endpoint && npm test -- reports-export
git merge --no-ff proj/csv-export/phase-2-export-button   && npm run typecheck && npm test -- reports-ui
git merge --no-ff proj/csv-export/phase-3-docs-cleanup    && npm run lint
# verify each Success Criterion, then:
```

## Stage 5 — Report & close
`.orchestrator/csv-export/REPORT.md` lists phases (all `complete`), evidence paths,
and the integration verification log. Open **one** PR from
`proj/csv-export/integration` with the spec's rollback plan in the body.

## Hard stop example
If P1 fails `npm test -- reports-export` three times, the orchestrator writes
`.orchestrator/csv-export/P1/BLOCKER.md` and `.orchestrator/csv-export/BLOCKER.md`
(`phase_acceptance_failed`), halts dependents (P2, P3 never start), and reports —
it does not mark anything done or open a PR.
