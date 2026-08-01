---
name: project-hardener
description: Drive an integrated project branch to near-perfect quality with a bounded convergence loop: detect failures (full suite, E2E, lint, typecheck), triage findings, run adversarial fixer and auditor passes, and prove zero regressions versus a pre-harden baseline. Use when the user says "harden this", "drive to near-perfect", "fix bugs and tighten before merge", "post-build convergence", or asks for final quality hardening after implementation.
---

# Project Hardener

Use this skill after build/integration work is complete and the goal is convergence,
not feature expansion. It runs a bounded quality loop that finds defects, fixes them
with evidence, and stops only at a verified fixpoint or an explicit blocker.

This skill is general-purpose. Repo-specific examples and verdict templates live in
[reference.md](reference.md).

## When to Use

- The project already has an implementation branch and needs post-build hardening.
- The user asks for phrases like "harden this", "drive to near-perfect", "fix bugs
  and tighten before merge", or "post-build convergence".
- You need a disciplined detect -> triage -> fix -> verify loop with regression
  protection against a baseline snapshot.

## When NOT to Use

- Early project discovery/spec work (use `project-researcher` / `project-orchestrator`).
- Single known defect with no broad convergence requirement (use `root-cause-debugger`).
- Open-ended enhancement work; this skill enforces a scope guard and blocks silent
  feature creep beyond the approved spec.

## Bounded Convergence Lifecycle

```text
Project Hardener — bounded loop
- [ ] 0) Capture pre-harden baseline snapshot
- [ ] 1) Detect: run full suite + E2E + lint + typecheck
- [ ] 2) Triage findings with taxonomy
- [ ] 3) Fix via fixer pass (test first, minimal diff)
- [ ] 4) Verify via independent read-only auditor pass
- [ ] 5) Run full-suite regression gate versus baseline
- [ ] 6) Repeat until near-perfect fixpoint or stop condition
```

## Edge-2 Intake Contract (from project-orchestrator)

Hardening starts from the orchestrator handoff package. Confirm these are present:

- integration branch reference
- approved `SPEC.md`
- per-phase evidence bundle (`patch.diff`, `NOTES.md`, `commands.log`, optional `BLOCKER.md`)
- integration verification evidence (`verify.log`, success-criteria status)
- loop budget and explicit hardening target

If any required handoff artifact is missing, halt and request a corrected handoff.

### Step 0 — Baseline snapshot (required)

Capture baseline once before the first hardening fix:

```bash
bash .cursor/skills/project-hardener/scripts/baseline-snapshot.sh \
  --out .orchestrator/<slug>/hardener/baseline.env
```

This baseline anchors regression diff checks for every loop.

### Step 1 — Detect

Run the full quality surface for each loop iteration:

- Full test suite
- E2E checks
- Lint
- Typecheck

Use the repo's canonical commands. The point is complete detection coverage, not
partial green checks.

### Step 2 — Triage taxonomy (mandatory)

Classify each finding into exactly one bucket:

- `bug`
- `UI-UX wiring`
- `missing-wiring`
- `gap`
- `regression`

Taxonomy details and examples are in [reference.md](reference.md).

### Step 3 — Fixer pass (role-based, adversarial)

Fixer role contract:

1. Reproduce the finding.
2. Add a regression test that fails first for the root cause.
3. Implement the smallest scoped fix.
4. Re-run the new regression test to green.
5. Report side-effect scan and touched surfaces.

The fixer must not bundle refactors or enhancements.

### Step 4 — Auditor pass (independent, read-only)

Auditor role contract:

1. Verify the regression test actually fails on pre-fix behavior and passes post-fix.
2. Confirm the test captures root cause, not just symptom.
3. Hunt side effects and scope creep independently.
4. Reject if evidence is incomplete or unrelated edits are present.

Auditor is read-only and must not edit files during verdict.

### Step 5 — Full-suite regression gate vs baseline

After each accepted fix, run full detection commands again and compare current results
to the pre-harden snapshot:

```bash
bash .cursor/skills/project-hardener/scripts/regression-diff.sh \
  --baseline .orchestrator/<slug>/hardener/baseline.env \
  --current .orchestrator/<slug>/hardener/current.env
```

Any new failure not present in baseline is a regression and blocks completion.

### Step 6 — Repeat (bounded)

Repeat detect -> triage -> fixer -> auditor -> regression gate until done-definition
is met or stop conditions fire.

## Near-Perfect Done-Definition (fixpoint)

Declare done only when all are true:

1. Every approved spec Success Criterion is green.
2. Full suite + E2E + lint + typecheck are clean.
3. Regression diff shows zero regressions versus pre-harden baseline.
4. No open high-severity findings remain.
5. The most recent full loop produced no new fixes (fixpoint iteration).

## Stop Conditions (hard stops)

Halt and report; never fabricate completion:

- `max_loops_reached`: loop count exceeds configured max N.
- `no_progress_or_oscillation`: repeated findings/fixes without net convergence.
- `unfixable_regression`: a regression cannot be resolved within loop budget.
- `evidence_missing`: required fail-then-pass or gate evidence is missing.
- `scope_guard_violation`: work expands beyond approved spec without escalation.

When stopped, emit a blocker report with evidence and recommended next action.

## Scope Guard and Edge-3 Escalation

Hardening is not silent enhancement.

If a finding requires design change beyond the approved spec:

1. Stop applying out-of-scope fixes.
2. Write an escalation note with defect evidence and why current spec is insufficient.
3. Route escalation to:
   - `project-orchestrator` for re-spec, or
   - `project-researcher` for re-research.
4. Include required payload: finding taxonomy/severity, attempted fixes, failed
   commands with exit codes, regression diff summary, and explicit decision request.

This is the loop-closing Edge-3 contract.

## Model Selection (role-based)

Use runtime role resolution, not hardcoded slugs:

| Role | Selection criteria | Responsibility |
|---|---|---|
| fixer | strongest available coding model at balanced speed | minimal fix + fail-then-pass regression test |
| auditor | capable model from a different family than fixer | independent read-only verification and rejection authority |
| mechanical | fastest low-cost model | taxonomy normalization, manifest updates, evidence formatting |

## Optional Manual Hook Wiring

If you want automatic rerun nudges after subagent completion, manually wire
`.cursor/hooks/verifier-rerun.sh` in local hook config. This skill does not edit
`.cursor/hooks.json`.

## Additional Resources

- Shared spine contract: [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Detailed taxonomy, role verdict templates, baseline mechanics, stop evidence:
  [reference.md](reference.md)
- Baseline script: [scripts/baseline-snapshot.sh](scripts/baseline-snapshot.sh)
- Regression diff script: [scripts/regression-diff.sh](scripts/regression-diff.sh)
- Related skills: [root-cause-debugger](../root-cause-debugger/SKILL.md),
  [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md),
  [autonomous-verifier](../autonomous-verifier/SKILL.md)
