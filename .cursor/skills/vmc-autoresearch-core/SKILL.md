---
name: vmc-autoresearch-core
description: Spine of ML Auto-Research for VMC critical domains (Chat, Swarm Reliability & Skills, To-Dos, Second-Brain). Enforces the 5-loop contract (investigate -> baseline-freeze -> research x3 -> implement + tighten x2) with VMC MCP lifecycle, scope-locked ownership manifests, null-hypothesis control arms, complexity-tagged model routing (mechanical tier roles for simple hypotheses, frontier tier roles for deep hypotheses), Postgres-backed holdout eval, and hard stop conditions. Generates per-domain eval/ template. Use when the user says "start autoresearch for <domain>", "run autoresearch loop", or work is happening on any autoresearch/<domain> branch.
---

# VMC AutoResearch Core

Use this skill to run a disciplined 5-loop ML Auto-Research cycle against a single VMC critical domain, producing frontier-level reliability gains with evidence and without breaking adjacent domains.

Canonical plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](.cursor/plans/vmc-autoresearch-platform.plan.md).

## When to Use

- Work is happening on an `autoresearch/<domain>` branch.
- User invokes an autoresearch trigger phrase for one of the 4 VMC critical domains: **chat**, **swarm**, **todos**, **second-brain**.
- An autoresearch loop gate must be evaluated before advancing.

## When NOT to Use

- Feature branches (use `autonomous-verifier` + `vmc-autopilot-oneshot` instead).
- Production (`master`) work.
- Any work outside the 4 declared domains until this skill's domain list is updated.

## Quick-Start Checklist

Copy and keep updated while running a loop:

```text
AutoResearch Loop Progress — domain=<DOMAIN>, loop=<N>
- [ ] 1) Verify branch is autoresearch/<domain>; load plan + ownership manifest
- [ ] 2) Read MCP schemas before any CallMcpTool (schema-first contract)
- [ ] 3) vmc_get_context(depth=full) + vmc_checkout_task(todoId=<loop-todoId>)
- [ ] 4) Run loop-specific action (per 5-Loop State Machine)
- [ ] 5) Enforce scope-lock: reject any patch touching files outside ownership.json
- [ ] 6) Score candidates via eval/harness.ts against Postgres holdout (verifier role only)
- [ ] 7) Run null-hypothesis control arm (re-run unchanged baseline, record variance)
- [ ] 8) vmc_report_progress at every gate; update research/loop-<N>/REPORT.md
- [ ] 9) Check Hard Stop Conditions; halt if any fire
- [ ] 10) Loop 4 -> Loop 5 transition requires Vince signature on MERGE_GATE.md
- [ ] 11) vmc_complete_task(loop-todoId) with evidence bundle before advancing
```

## MCP Schema-First Contract

Before any `CallMcpTool` invocation:

1. Read the tool descriptor JSON at `~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/<tool>.json`.
2. Confirm required arguments and allowed enum values.
3. Execute with explicit parameters (no guessing).
4. Persist tool output as evidence in `research/loop-<N>/REPORT.md`.

**Enforcement:** the hypothesis-execution subagent is not allowed to call MCP tools without this step. If a tool returns an auth error (`Invalid or missing API key`), halt and report — do not fabricate evidence.

## 5-Loop State Machine

Every domain project executes loops 0-5 in strict order. Each loop has required artifacts and a gate that must pass before advancing.

```text
Loop 0: Investigation   -> eval/ownership.json + research/loop-00/investigation.md
Loop 1: Baseline Freeze -> eval/baseline.json + Postgres holdout rows + eval/scorecard.md
Loop 2: Research Run 1  -> N candidate branches + research/loop-02/REPORT.md
Loop 3: Research Run 2  -> informed by loop-02 learnings + research/loop-03/REPORT.md
Loop 4: Research Run 3  -> research/loop-04/REPORT.md + MERGE_GATE.md (awaits Vince)
Loop 5: Implement+Tighten -> patches/ merged, 2 tightening iterations, final Tier-2
```

### Loop gate summary

| Loop | Advance iff |
|---|---|
| 0 | `ownership.json` committed; no out-of-scope file referenced in `investigation.md` |
| 1 | All Tier-1 tests green; `baseline.json` has p50/p95/p99 per pillar; holdout hash in `eval/holdout.ref.json` matches Postgres rows |
| 2 | >=1 hypothesis beats baseline on >=1 pillar beyond null-hypothesis variance; zero cross-domain regressions |
| 3 | same as loop 2 |
| 4 | same as loop 2 + **Vince signs `MERGE_GATE.md`** |
| 5 | All pillars >= baseline on holdout; Tier-2 green; `vmc_complete_task` called with evidence bundle; SOPs version-bumped |

Full gate commands, eval harness contract, and scoring math live in [reference.md](reference.md).

## eval/ Directory Contract

Every domain project creates this canonical shape before Loop 1:

```
eval/
├── ownership.json        # domain file globs; forbidden globs; readonly consume globs
├── models.json           # pinned model IDs per execution tier
├── baseline.json         # frozen metrics per pillar (p50/p95/p99)
├── holdout.ref.json      # hash reference to Postgres holdout rows
├── scorecard.md          # per-pillar SLA floors + scoring formula
├── fixtures/             # seeded prompts / replay inputs (seen by research agent)
└── harness.ts            # runs candidate vs baseline, emits scorecard
```

**Bootstrap command:** `~/.cursor/skills/vmc-autoresearch-core/scripts/init-eval.sh <domain> <worktree-path>`

Full schemas for each file are in [reference.md](reference.md).

## VMC Reporting Cadence

Every loop has its own `todoId` (from `vmc_get_roadmap(project="autoresearch")`):

1. **Loop start:** `vmc_checkout_task(todoId=<loop-todoId>)`.
2. **At each gate checkpoint:** `vmc_report_progress(todoId, progressPct, phase, evidence)`.
3. **Loop end:** `vmc_complete_task(todoId, evidence=<REPORT.md summary>, commitSha, filesChanged)`.

If VMC MCP returns auth error, **halt** and report the blocker. Do not proceed without VMC coordination — the whole point of the discipline is the audit trail.

## Model Routing by Complexity Tag

The frontier hypothesis generator tags each hypothesis. The orchestrator routes accordingly.

| Tag | Executor role (runtime-resolved) | Examples |
|---|---|---|
| `mechanical` | `mechanical_executor` | Refactors, renames, boilerplate, test scaffolding |
| `moderate` | `mechanical_executor` + `frontier_reviewer` | Single-file logic with clear spec |
| `deep` | `frontier_executor` | Multi-layer coordination, races, retrieval ranking, SSE/reconnect, anything Swarm |

**Swarm default = frontier** for every hypothesis unless explicitly tagged `mechanical`.

**Auto-escalation:** if a loop gate fails twice in a row with a mechanically
executed candidate on the same hypothesis line, auto-escalate to
`frontier_executor` and re-tag in `eval/models.json`.

Win-rate per tag is tracked in every `REPORT.md` and aggregated in `tasks/lessons.md`.

## Hard Stop Conditions

Any one triggers immediate halt + blocker report. Skill's integrated hooks parse this block:

```yaml
stop_if:
  loops_completed: ">= 5"
  stagnant_loops: ">= 2"               # no pillar improved beyond null-hypothesis variance
  cross_domain_regression: true        # adjacent domain contract suite fails
  schema_read_violation: true          # CallMcpTool without prior descriptor read
  scope_lock_violation: true           # patch touches file outside ownership.json
  token_budget_exceeded: true          # per-loop or per-project cap hit
  holdout_leak_detected: true          # seen_by_agent_at set on any holdout row
  vmc_auth_failure: true               # vmc_* returned "Invalid or missing API key"
```

On halt: write `research/loop-<N>/BLOCKER.md` with which condition fired, the evidence, and the recommended next human action.

## Scope-Lock Enforcement

Every candidate patch is validated against `eval/ownership.json` before it lands on `autoresearch/<domain>/loop-<N>/hyp-<M>`:

- `owns`: file globs the domain can write.
- `consumes_readonly`: globs it can read but not modify.
- `forbidden`: globs that, if touched, auto-reject the candidate.

See [reference.md](reference.md) for the `ownership.json` schema and the rejection diff format.

## Cross-Domain Safety

Before any Loop-5 merge:

1. Run the domain's Tier-1 contract suite (`npm test -- <domain>-contracts`).
2. Run **every other domain's** contract suite.
3. Run `apps/vmc-web/src/lib/vmc/__tests__/cross-domain/*.test.ts` (interface tests).
4. Run `scripts/validate.sh`.

Any failure blocks merge regardless of in-domain metrics.

## Human Gates (non-waivable)

- **Loop 4 -> Loop 5:** Vince must sign `MERGE_GATE.md` in the domain worktree. No auto-advance, no 24h-no-objection shortcuts.
- **Post-merge regression detected:** automatic rollback via `scripts/autoresearch-rollback.sh` to `autoresearch/<domain>-baseline-<timestamp>` tag.

## Completion Contract

Do not mark a loop or domain project complete until all are true:

- Tier-1 + Tier-2 tests passing with command evidence in `REPORT.md`.
- Null-hypothesis control arm run; variance recorded.
- Holdout scored via `plx_autoresearch_verifier` DB role; `seen_by_agent_at` tripwire still null on all rows.
- Per-pillar metrics >= baseline (per `scorecard.md` SLA floors).
- VMC `complete_task` call recorded with commit SHA + PR URL.
- `tasks/lessons.md` updated with win-rate by tag + any stop-condition fires + failure patterns.
- SOPs version-bumped per `update-sops-on-changes.mdc` if meaningful change.

## Additional Resources

- Full schemas, gate commands, scoring math: [reference.md](reference.md)
- Worked loop transcript (To-Dos pilot, loop 0 -> loop 2): [examples.md](examples.md)
- eval/ scaffold generator: [scripts/init-eval.sh](scripts/init-eval.sh)
- Parent plan: [.cursor/plans/vmc-autoresearch-platform.plan.md](.cursor/plans/vmc-autoresearch-platform.plan.md)
- Related skills: [autonomous-verifier](../autonomous-verifier/SKILL.md), [vmc-autopilot-oneshot](../vmc-autopilot-oneshot/SKILL.md)
