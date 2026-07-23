---
name: project-orchestrator
description: Turn a project request into an approved spec in one session, then execute it end-to-end as dependency-ordered phases in isolated git worktrees with delegated agents. Use when the user wants a large, multi-file, or multi-step effort planned and built autonomously, says "spec and execute", "run this as a project", "plan and build this", or hands over a feature, migration, or refactor that spans phases. Selects the best available models per role at runtime.
---

# Project Orchestrator

One contract, two halves: **plan once, execute autonomously.** Produce a project
**spec** the human approves in a single session, then run that spec end-to-end as
dependency-ordered **phases**, each in an isolated git worktree executed by a
delegated agent, integrated behind one PR.

This skill is general-purpose — it works in any repository. Repo-specific commands
(VMC verification, MCP lifecycle) live in [reference.md](reference.md).

## When to Use
- The work is large enough to need phases (multi-file feature, migration, refactor,
  greenfield module) and the user wants it planned and built with minimal back-and-forth.
- Trigger phrases: "spec and execute", "run this as a project", "plan and build this",
  "orchestrate this end-to-end".

## When NOT to Use
- A single-file or single-step change — just do it (or use `reliable-tdd-loop`).
- Pure investigation/debugging — use `codebase-investigation` / `root-cause-debugger`.
- One hypothesis, N competing solutions, scored by an eval harness — that's
  `parallel-multiagent-orchestrator` (this skill can call it for a competitive phase).

## Lifecycle

```text
Project Orchestrator — <slug>
- [ ] Stage 0  Calibrate intent (pre-plan-recalibrator)
- [ ] Stage 1  Draft SPEC.md (planner model + codebase-investigation)
- [ ] Stage 1  spec-validate.sh passes (sections, unique phase ids, DAG acyclic)
- [ ] Stage 2  Resolve model_plan; present SPEC + models; GET HUMAN APPROVAL
- [ ] Stage 3  Execute ready phases in isolated worktrees (bounded parallel)
- [ ] Stage 3  Per phase: scope-check + acceptance command exit 0
- [ ] Stage 4  Integrate phase branches in dependency order; full verify
- [ ] Stage 5  Handoff integration to project-hardener (Edge 2)
- [ ] Stage 6  Close or re-spec after hardener verdict
```

### Stage 0 — Calibrate
Run `pre-plan-recalibrator` to pin intent, constraints, success criteria, and
non-goals. Keep it short; the output feeds the spec.

### Stage 1 — Spec
Use the *planner* model and `codebase-investigation` to write a single
**`SPEC.md`** — the contract the user approves. Scaffold it with
`scripts/new-project.sh <slug>`; full template and field rules in
[reference.md §1](reference.md#1-spec-schema). The spec defines the **phase DAG**:
each phase has deliverables, `depends_on`, scope globs (`owns`/`forbidden`), an
**acceptance command** that must exit 0, a role, and a `competitive` flag.

If `.orchestrator/<slug>/RESEARCH.md` exists, consume it as Stage-1 input:
- use its recommendation to seed the proposed implementation direction
- use its candidate trade-offs to seed success criteria and phase boundaries
- preserve the same stage behavior when the file is absent

Validate before approval:
```bash
scripts/spec-validate.sh SPEC.md   # required sections, unique ids, deps exist, no cycles
```

### Stage 2 — Approval gate (one session, mandatory)
1. Resolve the **model plan** (see Model Selection below) and write it into the spec.
2. Present the full `SPEC.md` **and the resolved models** to the user.
3. **Do not execute anything until the user approves.** On approval, set
   `status: approved` + `approved_by`/`approved_at`. This is the only mandatory
   human gate — after sign-off the skill runs through integration autonomously.

### Stage 3 — Execute phases
Schedule phases by dependency (topological order); run phases whose `depends_on`
are all complete in parallel, capped by `budget.max_parallel_phases`.

For each ready phase, spawn one `best-of-n-runner` subagent (it provides the
isolated branch + worktree). For a `competitive: true` phase, spawn N and select a
winner via `parallel-multiagent-orchestrator`. Branch convention:
`proj/<slug>/phase-<k>-<name>`. The spawn-prompt contract (verbatim scope clauses,
artifacts, "produce a diff, do not merge") is in
[reference.md §3](reference.md#3-phase-execution).

Phase acceptance (orchestrator-run, not self-reported):
```bash
scripts/scope-check.sh "<owns globs>" "<forbidden globs>" <changed-files>   # scope-lock
<phase acceptance command>                                                  # must exit 0
```
On failure, retry up to `budget.max_attempts_per_phase`, then trip a hard stop.

### Stage 4 — Integrate
Merge phase branches into `proj/<slug>/integration` in dependency order. Run full
verification after each merge; resolve conflicts; then check every **Success
Criterion** in the spec. Details: [reference.md §4](reference.md#4-integration).

### Stage 5 — Named hardening handoff (Edge 2)
After integration verification passes, hand off to `project-hardener` with a
named artifact contract:

- integration branch name (`proj/<slug>/integration`)
- approved `SPEC.md` path
- per-phase evidence paths (`patch.diff`, `NOTES.md`, `commands.log`, `BLOCKER.md?`)
- integration verification artifacts (`verify.log`, success-criteria status)
- explicit near-perfect hardening target and loop budget

This handoff is required whenever post-build hardening is in scope.

### Stage 6 — Close or re-spec after hardener
If hardener converges, finalize the evidence bundle, update VMC lifecycle if
applicable (`vmc-sync`), and open **one integration PR** for the project.

If hardener emits Edge-3 escalation (out-of-spec design finding), do not scope-creep
inside hardening. Route escalation to:

- `project-orchestrator` re-spec path, and/or
- `project-researcher` re-research path,

then resume execution from the newly approved contract.

## Model Selection (role-based, runtime-resolved)

Name **roles**, never model slugs — so the skill always uses the best model
available at the time and never goes stale.

| Role | Selected by (criteria) | Used for |
|------|------------------------|----------|
| planner / scorer | most capable reasoning model w/ high thinking budget available now | spec, phase decomposition, winner scoring, review |
| builder | strongest coding model at balanced cost/speed | implementing a phase |
| mechanical | fastest low-cost model | refactors, renames, scaffolding |
| diversity / critic | a capable model from a *different family* than builder | competing candidate / independent review |

Resolution at the approval gate: **(1)** an override file if present
(`.orchestrator/<slug>/models.json`) → **(2)** else pick best-available-at-runtime
by the criteria above from the environment's model list → **(3)** show the choices
to the user to confirm/edit. Freeze the result into the spec's `model_plan` for the
run. Concrete slugs live only in the override file or the approved spec — never in
prose. Resolution details: [reference.md §2](reference.md#2-model-resolution).

## Gates

- **Drift** (reuse `vmc-autopilot-oneshot` detectors): scope drift (edits outside a
  phase's `owns`), plan drift (phase deviates from spec), evidence drift (a "done"
  claim with no passing acceptance command).
- **Hard stops** (halt + report, never fabricate): a phase fails acceptance
  `max_attempts_per_phase` times; a scope violation reaches integration; budget
  exceeded; dependency deadlock; integration regression; any auth/credential failure.
- **Human gate:** spec approval (Stage 2). No others.

## Closed-Loop Escalation (Edge 3)

`project-hardener` is allowed to halt and escalate when a high-severity finding
requires design change beyond the approved spec. Orchestrator ownership on
escalation:

1. capture escalation evidence into `.orchestrator/<slug>/BLOCKER.md` or phase notes
2. decide re-spec (`project-orchestrator`) vs. re-research (`project-researcher`)
3. update/re-approve the contract before re-entering build/hardening

## Reuse Map
`pre-plan-recalibrator` (calibrate) · `codebase-investigation` (spec research) ·
`autonomous-verifier` + `reliable-tdd-loop` (phase acceptance) ·
`parallel-multiagent-orchestrator` (best-of-N for a competitive phase) ·
`vmc-sync` (VMC lifecycle) · `vmc-autopilot-oneshot` (drift + evidence-bundle
validators) · `safe-deletion` / `dead-code-triage` (cleanup phases). This skill is
the spec/approval/DAG/integration **spine** that sequences them.

## Additional Resources
- Shared contract for all three spines: [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Spec schema, DAG rules, spawn contract, integration, model resolution: [reference.md](reference.md)
- Worked 3-phase end-to-end run: [examples.md](examples.md)
- Scaffold a project spec: [scripts/new-project.sh](scripts/new-project.sh)
- Validate a spec before approval: [scripts/spec-validate.sh](scripts/spec-validate.sh)
- Scope-lock a phase's changed files: [scripts/scope-check.sh](scripts/scope-check.sh)
