# Project Orchestrator — Reference

Detailed contracts loaded on demand from [SKILL.md](SKILL.md): the spec schema,
model resolution, phase execution, integration, and gates.

## 1. SPEC Schema

`SPEC.md` is the approved contract. `scripts/new-project.sh <slug>` scaffolds it.

### 1.1 Stage-1 input: optional `RESEARCH.md`

Before drafting `SPEC.md`, check for `.orchestrator/<slug>/RESEARCH.md`.

- If present, use it to seed Stage-1 drafting:
  - recommendation -> default implementation direction
  - candidate approaches/trade-offs -> phase alternatives, risks, and success criteria
- If absent, run Stage 1 exactly as before (no behavior change).

`RESEARCH.md` remains an input artifact only; `SPEC.md` is still the sole approved
execution contract.

```markdown
---
project: <slug>
created: <ISO>
status: draft | approved | executing | integrating | done | blocked
approved_by: <name>
approved_at: <ISO>
model_plan:                 # resolved + confirmed at the approval gate (§2)
  planner: <chosen>
  builder: <chosen>
  mechanical: <chosen>
  critic: <chosen>
budget:
  max_parallel_phases: 3
  max_attempts_per_phase: 3
  time_budget_min: 0        # 0 = unbounded
---

# <Project Title>

## Mission
<one paragraph: what and why>

## Success Criteria
- [ ] <measurable, verifiable outcome>

## Scope
- In: <what's included>
- Non-goals: <explicitly excluded>

## Phases

### P1 — <title>
- deliverables: <what exists when done>
- depends_on: []                       # phase ids that must complete first
- owns: ["src/feature/**"]             # globs this phase may write
- forbidden: ["src/legacy/**"]         # globs that auto-reject if touched
- acceptance: `<command that must exit 0>`
- role: builder | mechanical | deep
- competitive: false                   # true => best-of-N via parallel-multiagent-orchestrator

### P2 — <title>
- depends_on: [P1]
- ...

## Risks & Rollback
- <risk> -> <mitigation / how to roll back>

## Worktree Plan
- base branch: proj/<slug>
- phase branches: proj/<slug>/phase-<k>-<name>
- integration branch: proj/<slug>/integration
- delivery: one integration PR for the whole project
```

### Field rules (enforced by `spec-validate.sh`)
- Phase ids (`P1`, `P2`, …) are unique.
- Every `depends_on` entry references an existing phase id.
- The dependency graph is **acyclic** (validator runs a topological sort).
- Every phase has a non-empty `acceptance` command.
- `owns` is non-empty; `forbidden` may be empty.

## 2. Model Resolution

Roles are defined in [SKILL.md](SKILL.md#model-selection-role-based-runtime-resolved).
Resolve at the approval gate, in order:

1. **Override file** `.orchestrator/<slug>/models.json` (if present):
   ```json
   {
     "planner": "<slug>",
     "builder": "<slug>",
     "mechanical": "<slug>",
     "critic": "<slug>"
   }
   ```
   Use it verbatim. This is the deterministic/pinned path.

2. **Runtime best-available** (no override): enumerate the models available in the
   current environment and map each role by its criteria — most capable
   reasoning/thinking model → `planner`/`critic`; strongest balanced coding model →
   `builder`; fastest low-cost model → `mechanical`; for `critic`, prefer a
   **different model family** than `builder` to get independent review.

3. **Confirm with the human** at the approval gate: show the chosen role→model map,
   let the user edit, then freeze it into `model_plan` in the spec.

Rules:
- Never write a model slug into skill prose. Slugs live only in the override file or
  the approved spec's `model_plan`.
- If new models ship, update the override file (or re-resolve next run) — the skill
  body never needs editing.
- `validate-skills.sh` flags hardcoded slugs in any `SKILL.md` as a warning.

## 3. Phase Execution

### 3.1 Scheduling
Build the DAG from `depends_on`. A phase is **ready** when all its dependencies are
`complete`. Run ready phases concurrently up to `budget.max_parallel_phases`.

### 3.2 Spawn one runner per phase (one per candidate if competitive)
Use the `best-of-n-runner` subagent — it provides an isolated branch + worktree.

```
Task subagent_type=best-of-n-runner
     description="exec <Pk> <slug>"
     model=<model_plan[role]>
     run_in_background=true
     prompt="Implement phase <Pk> on branch proj/<slug>/phase-<k>-<name>.
             Scope (owns): <owns globs>. You may read anything; only WRITE within owns.
             Forbidden (auto-reject if touched): <forbidden globs>.
             Deliverables: <phase deliverables>.
             Required artifacts at .orchestrator/<slug>/<Pk>/:
               - patch.diff (git diff against proj/<slug>)
               - NOTES.md, commands.log
             Acceptance you must make pass locally: <acceptance command>.
             Produce the diff/commit on your branch. DO NOT merge.
             Stop after <max_attempts_per_phase> failed attempts and write BLOCKER.md."
```

### 3.3 Spawn-prompt contract (must appear verbatim)
1. `Scope (owns): <globs>. only WRITE within owns.`
2. `Forbidden (auto-reject if touched): <globs>.`
3. `Produce the diff/commit on your branch. DO NOT merge.`
4. `Stop after <N> failed attempts and write BLOCKER.md.`

### 3.4 Acceptance (orchestrator-run, never self-reported)
```bash
# scope-lock: changed files must be inside owns and avoid forbidden
git -C <phase-worktree> diff --name-only proj/<slug>... > /tmp/changed.txt
scripts/scope-check.sh "<owns>" "<forbidden>" $(cat /tmp/changed.txt)

# acceptance: the spec's command must exit 0
( cd <phase-worktree> && <acceptance command> )
```
Pass → mark phase `complete`. Fail → retry up to `max_attempts_per_phase`, then
hard stop `phase_acceptance_failed`.

## 4. Integration + Hardening Handoff

1. Create/checkout `proj/<slug>/integration` from the base branch.
2. Merge phase branches in **dependency order** (a valid topological order).
3. After each merge, run the integration verification (the union of touched phases'
   acceptance commands, or the repo's full check — see repo playbook below).
4. Resolve conflicts; if a merge breaks a previously-passing acceptance, hard stop
   `integration_regression`.
5. Verify every **Success Criterion** in the spec.
6. Produce the Edge-2 handoff package for `project-hardener` with:
   - integration branch name
   - approved `SPEC.md`
   - per-phase evidence paths
   - integration verification outputs
   - hardening target and loop budget
7. If hardening is complete, open **one integration PR** for the project. Include
   the rollback plan from the spec in the PR body.

## 5. Edge-3 Escalation Return Path

When `project-hardener` reports out-of-spec design findings, orchestration re-entry
is explicit:

1. Stop hardening-only fixes for that finding.
2. Ingest escalation payload (finding, attempted fixes, evidence, requested decision).
3. Route to:
   - re-spec in `project-orchestrator`, and/or
   - re-research in `project-researcher`.
4. Re-approve updated contract, then resume execution.

## 6. Drift Detectors & Hard Stops

Reuse the detector concept from `vmc-autopilot-oneshot`:

| Detector | Fires when |
|---|---|
| scope drift | a phase's changed files fall outside its `owns` or hit `forbidden` |
| plan drift | a phase's deliverables diverge from the spec without a spec update |
| evidence drift | a phase is marked done without a passing acceptance command |

Hard stops (halt all phases, write `.orchestrator/<slug>/BLOCKER.md`, report — never
fabricate progress):

```yaml
stop_if:
  phase_acceptance_failed:   ">= max_attempts_per_phase"
  scope_violation_merged:    true
  budget_exceeded:           true
  dependency_deadlock:       true   # no phase ready but project incomplete
  integration_regression:    true
  auth_or_credential_failure: true
```

## 7. Evidence Bundle

```
.orchestrator/<slug>/
├── SPEC.md                      # approved contract
├── models.json                  # optional override (if used)
├── P1/  { patch.diff, NOTES.md, commands.log, BLOCKER.md? }
├── P2/  ...
├── integration/ { verify.log, success-criteria.md, handoff.md? }
├── hardener/ { REPORT.md?, BLOCKER.md?, baseline.env?, current.env? }
└── REPORT.md                    # phases, statuses, evidence, PR link
```

## 8. Repo-specific playbook (agentic-swarm / VMC)

Use only when the working tree is the agentic-swarm / VMC repo:
- Phase acceptance / integration verification: `scripts/wterm-preflight.sh --mode pre-push`
  or `scripts/ci-local.sh`, plus `npm run typecheck --prefix apps/vmc-web` for VMC TS.
- VMC lifecycle per phase via `vmc-sync` (checkout/progress/complete with evidence).
- Honor `docs/REPO_HYGIENE_SPEC.md` for where artifacts/specs may live; the
  `.orchestrator/<slug>/` bundle is gitignored scratch unless promoted to an
  `artifacts/<domain>/<date-slug>/` evidence bundle.
- PR bodies touching critical modules need a `## Rollback Plan` (carry it from the spec).

## 9. Related Skills
- [`orchestration-kernel`](../orchestration-kernel/SKILL.md) — shared spine contract
- [`pre-plan-recalibrator`](../pre-plan-recalibrator/SKILL.md) — Stage 0 intent calibration
- [`codebase-investigation`](../codebase-investigation/SKILL.md) — spec research
- [`autonomous-verifier`](../autonomous-verifier/SKILL.md) — phase/integration acceptance
- [`reliable-tdd-loop`](../reliable-tdd-loop/SKILL.md) — test-first phases
- [`parallel-multiagent-orchestrator`](../parallel-multiagent-orchestrator/SKILL.md) — competitive phase (best-of-N)
- [`vmc-sync`](../vmc-sync/SKILL.md) — VMC lifecycle
