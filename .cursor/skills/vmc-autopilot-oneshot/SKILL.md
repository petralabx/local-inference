---
name: vmc-autopilot-oneshot
description: Dispatches a VMC AutoPilot phrase into either the legacy waterfall contract or the canary hybrid stage-gate contract across verifier, VMC MCP lifecycle, reliable TDD loops, composed parallel orchestration, drift gates, evidence bundles, and merge gates. Use when the user says VMC AutoPilot, oneshot, P-A to P-E, Hybrid P-A to P-E, or asks to run reliability phases autonomously.
---
# VMC AutoPilot OneShot

Use this skill to expand a short trigger phrase into the full implementation contract. Legacy phrases stay on the waterfall path until the hybrid canary is accepted; explicit Hybrid aliases route through the stage-gate contract.

## Accepted Trigger Formats

Legacy waterfall:

- `Run VMC AutoPilot Phase {A|B|C|D|E}: {goal}`
- `VMC AutoPilot P{A|B|C|D|E} :: {goal}`
- `VMC_WATERFALL_AUTOPILOT phase={A-E} goal="{goal}" branch="{branch}"`

Hybrid canary:

- `Run VMC AutoPilot Hybrid Phase {A|B|C|D|E}: {goal}`
- `VMC AutoPilot Hybrid P{A|B|C|D|E} :: {goal}`
- `VMC_HYBRID_AUTOPILOT phase={A-E} goal="{goal}" branch="{branch}"`

Rollback is alias-level: remove or stop using the Hybrid trigger lines above and legacy phrases continue to emit the waterfall contract.

## Shared Preconditions

Before either path edits files:

1. Apply reliability workflow first:
   - `.cursor/skills/autonomous-verifier/SKILL.md`
   - `.cursor/rules/reliability-verification.mdc`
   - `.cursor/skills/vmc-sync/SKILL.md`
   - `.cursor/skills/reliable-tdd-loop/SKILL.md` when behavior changes require tests
   - `.cursor/rules/agent-testing-contract.mdc`
   - `.cursor/rules/local-ci-before-push.mdc`
   - `.cursor/rules/surgical-changes.mdc`
2. Enforce MCP schema-first behavior before any MCP tool call.
3. Enforce VMC lifecycle:
   - `vmc_get_context(depth=full)`
   - `vmc_checkout_task`
   - `vmc_report_progress` at each checkpoint
   - `vmc_get_repo_health` and `vmc_get_dependency_risks` before merge gate
   - `vmc_complete_task` only after evidence gates pass
4. Use `.cursor/skills/autonomous-verifier/scripts/validate.sh` plus the repo-required preflight gates when committing or pushing.

## Legacy Waterfall Contract

When a legacy trigger is detected, enforce all items below in order.

1. Enter phase-scoped waterfall mode:
   - One PR per phase
   - No cross-phase edits without explicit scope update
   - Prefer `.cursor/plans/vmc_reliability_waterfall_plan_448e5e77.plan.md` when present
   - Otherwise use an explicit phase brief in the user request as the gate source
2. Enforce reliable TDD grind loop:
   - Add failing contract test first
   - Implement minimal fix
   - Refactor safely
   - Re-run verification matrix
3. Use parallel support only when complexity warrants and only through `.cursor/skills/parallel-multiagent-orchestrator/SKILL.md`.
4. Require final evidence bundle:
   - test/lint/typecheck/validate outputs
   - browser snapshot evidence for UI changes
   - VMC call evidence
   - metric deltas and residual risks
5. Run babysit loop until merge-ready:
   - comments triaged
   - CI green
   - blockers documented

## Hybrid Stage-Gate Contract

When a Hybrid trigger is detected, enforce this loop for the selected phase.

1. `PhaseGateEntry`
   - Read the latest `gate_entry` and `gate_exit` records from `.cursor/plans/ledger/<branch>/ledger.jsonl` before any edit.
   - If the ledger is absent or inconsistent, enter rehydration mode and halt until the operator supplies state.
   - Declare phase, branch, ownership globs, evidence directory, baseline artifact, and active gate source.
2. `PlanStep`
   - Write the active step list and `plan_hash`.
   - Keep one active objective at a time.
   - Log a `plan` entry before execution begins.
3. `ExecStep`
   - Stay inside declared ownership globs.
   - Maximum intra-phase iterations: `5`.
   - Maximum wall-clock without gate transition: `45 minutes`.
   - Heartbeat cadence: every `10 minutes` or every VMC checkpoint, whichever is sooner.
4. `VerifyStep`
   - Run the applicable verifier, TDD, browser, MCP, and preflight checks.
   - Write or refresh all required files in `artifacts/autopilot/<yyyy-mm-dd>-<phase-lower>-<slug>/`.
   - Invoke every drift detector named in `reference.md`; a missing detector fails the gate.
   - Run the skill-local validation helpers in `scripts/` before phase exit.
5. `DriftTriage`
   - Scope drift: revert out-of-scope edits, then replan inside ownership.
   - Plan drift: pause and realign the active plan before continuing.
   - Evidence drift: rerun the verification matrix.
   - Context drift: halt for rehydration.
   - Model drift: apply the composed orchestrator's executor-tier rule only when a numeric null-hypothesis control arm exists.
6. `ReplanCapOrHashRepeat`
   - `replan_rate` is informational, alerting when it exceeds `2` per phase.
   - A second consecutive identical `plan_hash` halts the phase.
   - Never silently continue after a loop cap breach.
7. `PhaseGateExit`
   - All success metrics in `reference.md` must have numeric results or an explicit `not_applicable` rationale allowed by that metric.
   - Required evidence files: `REPORT.md`, `artifacts.json`, `commands.log`, `mcp-evidence.json`, `metrics.json`, `ledger-snapshot.jsonl`, `risks.md`.
   - Append a `gate_exit` ledger record only after all hard targets pass.

## Hybrid Parallel Composition

Oneshot does not redefine parallel orchestration primitives. When parallel lanes are warranted, invoke `.cursor/skills/parallel-multiagent-orchestrator/SKILL.md` and inherit its scope-lock, winner rubric, null-hypothesis control arm, model routing, and cross-domain regression checks.

AutoPilot supplies only these integration constraints:

- If two lanes declare overlapping `owns` globs, serialize them before writes.
- Only the orchestrator writes shared artifacts: ledger, evidence bundle index, phase metrics.
- Lanes write under their own `hyp-<M>/` subtrees and hand off via diff.
- Each lane has exactly one role at a time: `explore`, `execute`, or `verify`.
- Every spawned lane must report terminal state before phase exit.

## OneShot Templates to Emit

When asked for the legacy waterfall prompt, output this template:

```text
Run VMC_WATERFALL_AUTOPILOT for phase={PHASE} goal="{GOAL}" branch="{BRANCH}".

Apply and enforce:
1) .cursor/skills/autonomous-verifier/SKILL.md
2) .cursor/rules/reliability-verification.mdc
3) .cursor/plans/vmc_reliability_waterfall_plan_448e5e77.plan.md (phase-scoped)

Execution contract:
- One PR per phase, no cross-phase edits.
- Before any CallMcpTool: read schema descriptor first.
- VMC lifecycle: get_context(full) -> checkout -> report_progress -> repo_health+dependency_risks -> complete(with evidence).
- TDD loop: failing test first, then implementation, then refactor.
- Run .cursor/skills/autonomous-verifier/scripts/validate.sh and full verification matrix.
- Babysit PR to green.
- Output REPORT evidence: commands, exit codes, metrics, MCP proofs, risks.
```

When asked for the hybrid prompt, output this template:

```text
Run VMC_HYBRID_AUTOPILOT for phase={PHASE} goal="{GOAL}" branch="{BRANCH}".

Apply and enforce:
1) .cursor/skills/autonomous-verifier/SKILL.md
2) .cursor/rules/reliability-verification.mdc
3) .cursor/skills/reliable-tdd-loop/SKILL.md when behavior changes require tests
4) .cursor/skills/parallel-multiagent-orchestrator/SKILL.md only by composition
5) .cursor/skills/vmc-autopilot-oneshot/reference.md detector, ledger, evidence, and metric schemas

Execution contract:
- Enter PhaseGateEntry and read .cursor/plans/ledger/{BRANCH}/ledger.jsonl before edits.
- Execute PlanStep -> ExecStep -> VerifyStep -> DriftDetectors -> PhaseGateExit.
- Enforce max 5 intra-phase iterations, max 45 minutes without gate transition, heartbeat every 10 minutes.
- Halt on second consecutive identical plan_hash.
- Write artifacts/autopilot/<yyyy-mm-dd>-<phase-lower>-<slug>/ with REPORT.md, artifacts.json, commands.log, mcp-evidence.json, metrics.json, ledger-snapshot.jsonl, risks.md.
- Run scripts/validate-evidence-bundle.py, scripts/validate-ledger.py, and scripts/validate-detectors.py before phase exit.
- Do not call vmc_complete_task until phase-exit metrics pass.
```

## Auto-Parse Rules

If the user omits branch:

- derive: `feat/vmc-reliability/phase-{phase-lower}-{slugified-goal}`

If the user omits phase:

- ask for phase before execution.

If scope is ambiguous:

- ask one clarifying question and pause.

If mode is omitted:

- use legacy waterfall unless the trigger explicitly includes `Hybrid` or `VMC_HYBRID_AUTOPILOT`.

## Additional Resources

- Phrase variants and copy-paste aliases: [examples.md](examples.md)
- Contract details and phase mapping guide: [reference.md](reference.md)
