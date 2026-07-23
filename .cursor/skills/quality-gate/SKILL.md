---
name: quality-gate
description: Orchestrates engineering quality workflows across debugging, verification, refactoring, safe deletion, TDD, CI, and release readiness. Use when the user asks to make work production ready, run a quality gate, harden changes, review risk, debug deeply, verify implementation, or prepare for merge.
---

# Quality Gate

Use this skill as the entry point for quality-critical work. It does not replace focused skills; it selects and composes them, then enforces a final evidence-based gate.

This skill is global and self-contained. When sibling skills are available, use them. When they are not, apply the fallback gates here.

## Trigger Phrases

Use when the user says:

- run the quality gate
- make this production ready
- harden this
- verify this implementation
- prepare this for merge
- review risk
- debug this properly
- refactor safely
- clean this up without breaking behavior

## Route The Work

Classify the request before editing:

| Risk Shape | Use When Available | Fallback |
|---|---|---|
| Bug, regression, unexplained failure | `root-cause-debugger` | Reproduce, isolate, prove root cause, fix smallest surface |
| New behavior or reliability change | `reliable-tdd-loop` | Add or identify failing/contract test before implementation |
| Complex implementation or integration | `autonomous-verifier` | Baseline, scoped edit, full verification matrix, evidence report |
| Behavior-preserving simplification | `isomorphic-refactor` | Fill isomorphism card, one lever, prove no behavior drift |
| Dead code or deletion | `dead-code-triage`, `safe-deletion` | Search references, dynamic/config/test/docs/barrels, ask before file deletion |
| Large parallelizable scope | `parallel-multiagent-orchestrator` | Split by ownership; one owner per path; synthesize before editing |
| VMC-tracked work | `vmc-sync`, `vmc-autopilot-oneshot` | Check context if tools exist; otherwise record MCP/tool gap |
| Pre-push or CI confidence | `wterm-preflight`, `babysit` | Run focused checks, then broader local/CI checks |

If more than one risk shape applies, use the strictest gate first: bug reproduction before refactor, deletion proof before removal, behavior proof before simplification, and integration verification before completion.

## Mandatory Quality Loop

1. **Define done**: state the expected behavior, files/systems in scope, and the risk shape.
2. **Baseline**: capture current tests, lints, typecheck, build, logs, or reproduction. If a command cannot run, record why.
3. **Plan narrow work**: choose the sibling workflow or fallback. Keep one objective active.
4. **Execute minimal change**: edit the smallest surface that can satisfy the evidence.
5. **Verify focused**: run the narrowest checks that prove the changed behavior.
6. **Verify broad**: run broader smoke/type/lint/build/CI checks appropriate to the blast radius.
7. **Review risk**: inspect for regressions, unsafe deletion, behavior drift, secrets, auth, data migration, and observability gaps.
8. **Close out**: report commands, outcomes, risks, rollback, and any work not done.

## Fallback Gates

### Debugging Gate

- Reproduce the failure or capture the exact missing evidence.
- Form one hypothesis at a time.
- Prove the fix against the reproduction.
- Do not refactor while debugging unless the refactor is required to expose the bug.

### TDD And Behavior Gate

- For new or changed behavior, write or identify a failing/contract test first when practical.
- For refactors, use characterization tests or golden output when existing tests are weak.
- Never accept "looks cleaner" as evidence.

### Refactor Gate

- Preserve observable behavior.
- Use one refactor lever per change.
- Avoid broad codemods, regex rewrites, unrelated renames, formatting churn, or drive-by fixes.
- If equivalence is uncertain, stop and create an isomorphism card.

### Deletion Gate

- Do not delete files without explicit user approval.
- Search direct references, dynamic imports, string/config references, docs, tests, generated registries, route handlers, and barrel re-exports.
- Classify candidates as `true_positive`, `false_positive`, or `deferred`.
- Defer when runtime registration, ownership, or external consumers are unclear.

### Integration Gate

- Verify auth, environment, schema, and API contracts before calling an external service.
- Read MCP tool schemas before MCP calls.
- Never print secrets; report presence/length or sanitized status only.
- For DB or production-affecting work, verify staging/context guard first.

### CI And Merge Gate

- Focused checks must pass before broad checks.
- Broad checks must not introduce new lint/type/test failures.
- If CI or review comments exist, triage every signal before claiming ready.
- Do not mark complete with unverified assumptions; list residual risk instead.

## Output Contract

For quality-critical work, final response or artifact must include:

- Scope and risk shape.
- Sibling skills or fallback gates used.
- Baseline evidence.
- Changed behavior or refactor/deletion candidate IDs.
- Verification commands and outcomes.
- Remaining risks, blocked checks, and rollback notes.

Use `quality-checklist.md` during execution and `quality-closeout.md` for the final evidence summary.
