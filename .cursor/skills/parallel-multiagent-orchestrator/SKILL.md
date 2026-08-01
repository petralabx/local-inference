---
name: parallel-multiagent-orchestrator
description: Orchestrates N parallel hypothesis candidates per ML Auto-Research loop using best-of-n-runner subagents on isolated worktrees (autoresearch/<domain>/loop-<N>/hyp-<M> branches). Enforces scope-lock via ownership.json, scores via eval/harness.ts, and selects winners with regression checks plus human approval rubrics. Model routing is role-based and resolved from eval/models.json at runtime (mechanical tier for simple candidates, frontier tier for deep candidates, diversity tier for anti-bias arms). Use inside any autoresearch loop 2-4, or when the user says "run parallel candidates", "spawn best-of-n", or is orchestrating multi-candidate research.
---

# Parallel Multiagent Orchestrator

Use this skill to run **N parallel hypothesis candidates per research loop** in isolated worktrees via `best-of-n-runner`, route each candidate by complexity tag to the right model tier, enforce scope-lock, and select a winner by rubric — all without leaking work across candidates or across domains.

Canonical plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](.cursor/plans/vmc-autoresearch-platform.plan.md) (Phase 3 scope).

## When to Use

- Inside autoresearch loops **2, 3, or 4** for any of the 4 VMC critical domains (`chat`, `swarm`, `todos`, `second-brain`).
- User invokes an explicit orchestration phrase: `run parallel candidates for <domain> loop <N>`, `spawn best-of-n for <domain> loop <N>`, `pick winner loop <N>`.
- Hypothesis generator has emitted `research/loop-<N>/hypotheses.md` with >=1 hypothesis tagged `mechanical`/`moderate`/`deep`.

## When NOT to Use

- Loop 0 (investigation) or Loop 1 (baseline freeze) — use `vmc-autoresearch-core` directly.
- Loop 5 (implementation + tightening) — use `reliable-tdd-loop` for the grind loop on the winning patch.
- Feature branches or production work — use `autonomous-verifier` + `vmc-autopilot-oneshot`.
- Any domain outside the 4 declared domains until this skill's domain list is updated.
- When `eval/ownership.json` is missing or `eval/baseline.json` has not yet been frozen.

## Quick-Start Checklist

Copy and keep updated while orchestrating a loop:

```text
Parallel Orchestrator Progress — domain=<DOMAIN>, loop=<N>, candidates=<K>
- [ ] 1) Verify branch is autoresearch/<domain>; eval/ownership.json + eval/baseline.json present
- [ ] 2) Read MCP schemas before any CallMcpTool (schema-first contract)
- [ ] 3) vmc_checkout_task for the parent loop todoId (e.g. ar-<domain>-l<N>)
- [ ] 4) Load research/loop-<N>/hypotheses.md; confirm each has a complexity tag
- [ ] 5) For each hypothesis, create branch autoresearch/<domain>/loop-<N>/hyp-<M>
- [ ] 6) Spawn one best-of-n-runner per hypothesis with model from eval/models.json executor_by_tag
- [ ] 7) Each subagent does its own vmc_checkout_task with a unique hyp-level todoId
- [ ] 8) On each candidate patch: run .cursor/hooks/scope-lock.sh; reject out-of-scope
- [ ] 9) Score each candidate via eval/harness.ts --mode=score (passing candidates only)
- [ ] 10) Run null-hypothesis control arm (re-run unchanged baseline under same conditions)
- [ ] 11) Run cross-domain regression check (every other domain's contract suite)
- [ ] 12) Apply winner-selection rubric; write research/loop-<N>/REPORT.md + scorecard.md
- [ ] 13) Check auto-escalation rule (double-fail on same hypothesis line => frontier)
- [ ] 14) Record per-tag win rate in REPORT.md; aggregate in tasks/lessons.md
- [ ] 15) vmc_report_progress at every gate; vmc_complete_task only after winner merges
```

## MCP Schema-First Contract

Before any `CallMcpTool` invocation, the orchestrator and every spawned subagent must:

1. Read the tool descriptor JSON at `~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/<tool>.json`.
2. Confirm required arguments and allowed enum values.
3. Execute with explicit parameters — no guessing.
4. Persist tool output as evidence under `research/loop-<N>/hyp-<M>/`.

Schema violations trip the `schema_read_violation` hard stop defined in [`vmc-autoresearch-core`](../vmc-autoresearch-core/SKILL.md#hard-stop-conditions). If a VMC tool returns `Invalid or missing API key`, halt and report — do not fabricate evidence.

## 1. Spawn Pattern

One `best-of-n-runner` subagent per hypothesis, one branch per candidate, one worktree per branch. Parallelism is structural — no candidate can see another's patch until scoring.

### Branch naming (canonical)

```
autoresearch/<domain>/loop-<N>/hyp-<M>
```

- `<domain>`: `chat` | `swarm` | `todos` | `second-brain`
- `<N>`: zero-padded loop index (`02`, `03`, `04`)
- `<M>`: zero-padded hypothesis index (`01`, `02`, ...), matching the `hypotheses.md` numbering.

### Spawn template

For each hypothesis `H<M>` with tag `<tag>` in `research/loop-<N>/hypotheses.md`:

```
Task subagent_type=best-of-n-runner
     description="exec H<M> <tag> <domain> L<N>"
     model=<model-id-from-eval/models.json.executor_by_tag[tag]>
     prompt="Execute hypothesis H<M> on branch autoresearch/<domain>/loop-<N>/hyp-<M>.
             Scope: eval/ownership.json (owns + consumes_readonly only).
             Forbidden: any file matching eval/ownership.json .forbidden.
             Required artifacts at /hyp-<M>:
               - patches/hyp-<M>.patch (git diff against loop-<N> parent)
               - research/loop-<N>/hyp-<M>/NOTES.md
               - research/loop-<N>/hyp-<M>/commands.log
             Do own vmc_checkout_task for todoId=ar-<domain>-l<N>-h<M> before first edit.
             Do own vmc_report_progress at midpoint.
             Do NOT run eval/harness.ts --mode=score yourself; the orchestrator scores.
             Do NOT merge; produce the diff only.
             Stop after 4 failed attempts and write research/loop-<N>/hyp-<M>/BLOCKER.md."
     run_in_background=true
```

Parallelism cap: **N = 2 candidates per loop** is the default (per plan Resolved Decision #1). Raise only if loop-2 variance demands and after budget review.

Full spawn matrix + commands: [reference.md §1](reference.md#1-spawn-matrix--commands).

## 2. Scope-Lock Enforcement (`ownership.json`)

Every candidate patch is validated against `eval/ownership.json` **before** it is eligible for scoring. A scope-lock violation auto-rejects the candidate and contributes `-5` per violation to `loop_score`.

### Enforcement points

1. **Spawn-time guard (advisory):** the subagent is told its ownership globs in its prompt.
2. **Pre-score gate (binding):** `.cursor/hooks/scope-lock.sh <domain> <patch-path>` is run by the orchestrator before `eval/harness.ts --mode=score`. Non-zero exit => candidate rejected, archived under `research/loop-<N>/rejected/hyp-<M>/`.
3. **Pre-merge gate (Loop 5 final):** re-run on the winning merged patch. Any violation at this point trips `scope_lock_violation` hard stop.

### Manifest keys (reference)

- `owns`: file globs the domain can write.
- `consumes_readonly`: globs it can read but not modify.
- `forbidden`: globs that, if touched, **auto-reject**.

Schema and example manifest: [`vmc-autoresearch-core/reference.md §2.1`](../vmc-autoresearch-core/reference.md#evalownershipjson). Scope-lock script shipped with this skill: [`scripts/scope-lock.sh`](scripts/scope-lock.sh) (mirrors the canonical `.cursor/hooks/scope-lock.sh`).

## 3. Winner-Selection Rubric

Apply in strict order. Any step failing disqualifies the candidate.

### Step A — Gate filters (binary pass/fail)

1. Scope-lock passed (§2).
2. Tier-1 domain contract suite green: `npm test -- <domain>-contracts`.
3. Cross-domain regression check green: every **other** domain's contract suite still passes.
4. Null-hypothesis control arm re-run and variance recorded.

### Step B — Scoring (quantitative)

Per-pillar improvement measured in null-hypothesis-variance units (from `eval/baseline.json`):

```
pillar_improvement = (candidate_metric - baseline_metric) / null_hypothesis_variance
```

Aggregate:

```
loop_score =  sum(pillar_improvement for each pillar)
           - 10 * count(cross_domain_regressions)
           - 100 * any_holdout_leak
           - 5  * count(scope_lock_violations)
```

Winner = candidate with max `loop_score` that also passes Step A **and** meets `pass_threshold` in `eval/scorecard.md`. Below threshold => stagnant loop, no winner declared.

### Step C — Human approval rubric (Loop 4 → Loop 5 only)

Before Loop 5 implementation begins, the frontier merge-gate reviewer produces `MERGE_GATE.md` with this checklist, which **Vince must sign**:

```markdown
# MERGE_GATE — <domain> loop 04 → loop 05

## Winner Summary
- Candidate: hyp-<M>
- Tag: <mechanical|moderate|deep>
- Executor: <model-id>
- loop_score: <value>  (pass_threshold: <threshold>)

## Evidence Bundle
- [ ] Tier-1 contract suite passing (paste command output)
- [ ] Cross-domain contract suites passing
- [ ] Null-hypothesis variance delta > 1 unit on >=1 pillar
- [ ] Scope-lock clean; no forbidden globs touched
- [ ] Holdout tripwire (seen_by_agent_at) still null on all rows
- [ ] All 3 research runs' REPORT.md reviewed (loops 02, 03, 04)
- [ ] Model routing matches eval/models.json; no manual override

## Risk Notes
(Reviewer fills.)

## Approved by
- Name: Vince Sachet
- Date: ____________
- Signature: ____________
```

No auto-advance. No 24h-no-objection shortcut. See [`vmc-autoresearch-core` Human Gates](../vmc-autoresearch-core/SKILL.md#human-gates-non-waivable).

## 4. Model Routing by Complexity Tag

The frontier hypothesis generator tags each hypothesis in `research/loop-<N>/hypotheses.md`. The orchestrator reads `eval/models.json.executor_by_tag` and routes accordingly.

| Tag | Executor role (runtime-resolved) | Rationale |
|---|---|---|
| `mechanical` | `mechanical_executor` | Refactors, renames, boilerplate, test scaffolding |
| `moderate` | `mechanical_executor` + `frontier_reviewer` | Single-file logic with clear spec |
| `deep` | `frontier_executor` | Multi-layer coordination, races, retrieval ranking, SSE/reconnect |

### Swarm override

For `domain=swarm`, the executor defaults to frontier for **every** hypothesis
unless explicitly tagged `mechanical` (see
`eval/models.json.swarm_default_executor_role`).

### Diversity arm (loops 3-4 only)

For non-`deep` hypotheses in loops >=3, spawn a **second** candidate with
`eval/models.json.diversity_alternate_executor_role` to avoid single-model bias.
Scored the same way; doubles candidate count on that hypothesis line.

### Auto-escalation

If a loop gate **fails twice in a row** with a mechanically executed candidate on
the same hypothesis line:

1. Auto-escalate that hypothesis line to `frontier_executor` for the next attempt.
2. Record the re-tag decision in `eval/models.json` with an ISO timestamp note.
3. Log in `research/loop-<N>/REPORT.md` under `## Auto-Escalations`.

### Win-rate tracking

Every `research/loop-<N>/REPORT.md` ends with:

```yaml
win_rate_by_tag:
  mechanical: { attempts: <N>, winners: <W>, rate: <W/N> }
  moderate:   { attempts: <N>, winners: <W>, rate: <W/N> }
  deep:       { attempts: <N>, winners: <W>, rate: <W/N> }
executor_win_rate:
  mechanical_executor:          { attempts: <N>, winners: <W> }
  frontier_executor:            { attempts: <N>, winners: <W> }
  diversity_alternate_executor: { attempts: <N>, winners: <W> }
```

`tasks/lessons.md` aggregates across domains so we learn where composer is actually sufficient vs where it isn't. Data beats guess.

## 5. VMC Coordination Per Subagent

Each spawned `best-of-n-runner` owns its own VMC lifecycle, using a hypothesis-level todoId derived from the parent loop todoId.

### Todo ID convention

```
Parent loop:   ar-<domain>-l<N>        (e.g. ar-todos-l02)
Hypothesis:    ar-<domain>-l<N>-h<M>   (e.g. ar-todos-l02-h01)
Winner merge:  ar-<domain>-l<N>-win    (owned by orchestrator, not subagent)
```

### Per-subagent lifecycle (inside the `best-of-n-runner` prompt)

1. **Before first edit:** `vmc_checkout_task(todoId="ar-<domain>-l<N>-h<M>")`.
2. **Midpoint (after scope-lock-clean diff exists):** `vmc_report_progress(todoId, progressPct=50, phase="candidate-scored-ready", evidence=<path-to-NOTES.md>)`.
3. **On stop/blocker:** `vmc_report_progress(todoId, phase="blocked", evidence=<path-to-BLOCKER.md>)` — do NOT call `vmc_complete_task`.
4. **On clean-diff emitted:** subagent exits; orchestrator is responsible for `vmc_complete_task` after scoring.

### Orchestrator lifecycle

1. **Loop start:** `vmc_checkout_task(todoId="ar-<domain>-l<N>")`.
2. **After all candidates scored:** `vmc_report_progress` with per-candidate scorecard summary.
3. **Winner merged to `autoresearch/<domain>/loop-<N>`:** `vmc_complete_task(todoId="ar-<domain>-l<N>", evidence=<REPORT.md>, commitSha=<merge-sha>, filesChanged=<list>)` and also `vmc_complete_task` for each candidate's hypothesis todoId (winner + rejected alike, with outcome recorded).

If VMC MCP returns auth error at any point: **halt** the affected agent and report the blocker; do not fabricate progress.

## 6. Hard Stop Conditions (inherited + orchestrator-specific)

Any one triggers immediate halt across all running candidates and writes `research/loop-<N>/BLOCKER.md`.

Inherited from [`vmc-autoresearch-core`](../vmc-autoresearch-core/SKILL.md#hard-stop-conditions):

```yaml
stop_if:
  loops_completed:         ">= 5"
  stagnant_loops:          ">= 2"
  cross_domain_regression: true
  schema_read_violation:   true
  scope_lock_violation:    true   # any candidate merged (not just rejected)
  token_budget_exceeded:   true
  holdout_leak_detected:   true
  vmc_auth_failure:        true
```

Orchestrator-specific additions:

```yaml
stop_if:
  candidate_spawn_failure:     ">= 2"   # best-of-n-runner fails to start twice
  all_candidates_rejected:     true     # no winner after rubric; loop stagnant
  auto_escalation_count:       ">= 3"   # in a single loop, signals mis-tagged hypotheses
```

On halt: write `research/loop-<N>/BLOCKER.md` per [`vmc-autoresearch-core/reference.md §8`](../vmc-autoresearch-core/reference.md#8-stop-condition-evidence-format) and `vmc_report_progress` with `phase="blocked"`.

## 7. Reporting Artifacts

Every orchestrated loop produces this canonical shape under the domain worktree:

```
research/loop-<N>/
├── hypotheses.md              # from frontier generator (pre-existing)
├── hyp-01/
│   ├── NOTES.md               # subagent's own log
│   ├── commands.log           # every shell command run
│   └── BLOCKER.md             # present only if subagent halted
├── hyp-02/
│   └── ...
├── rejected/                  # scope-lock or Tier-1 failures archived here
├── scorecard-hyp-01.json      # eval/harness.ts output
├── scorecard-hyp-02.json
├── scorecard-null.json        # null-hypothesis control arm
├── REPORT.md                  # winner decision + rubric evidence + win-rate block
└── patches/
    └── winner.patch           # symlink or copy of winning hyp-<M>.patch
```

REPORT.md schema: [reference.md §3](reference.md#3-reportmd-schema).

## 8. Completion Contract

Do not declare a research loop complete (`vmc_complete_task` on `ar-<domain>-l<N>`) until **all** are true:

- Every hypothesis has a terminal state: `winner`, `rejected-score`, `rejected-scope`, or `blocker`.
- `research/loop-<N>/REPORT.md` committed with rubric evidence, scorecards, and win-rate block.
- Null-hypothesis control arm ran and variance recorded.
- Cross-domain contract suites green (all four domains).
- Scope-lock clean on the winner diff.
- `tasks/lessons.md` updated with tag win-rate observations + any stop-condition fires.
- (Loop 4 only) `MERGE_GATE.md` signed by Vince before Loop 5 begins.

## Additional Resources

- Spawn matrix, REPORT.md schema, scoring math, auto-escalation log format: [reference.md](reference.md)
- Worked transcripts (2-candidate mock loop; scope-lock rejection; auto-escalation): [examples.md](examples.md)
- Mock loop runner for smoke-testing the skill: [scripts/mock-loop.sh](scripts/mock-loop.sh)
- Scope-lock enforcement script: [scripts/scope-lock.sh](scripts/scope-lock.sh)
- Winner picker (reads scorecards, emits REPORT.md stub): [scripts/pick-winner.sh](scripts/pick-winner.sh)
- Parent plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](.cursor/plans/vmc-autoresearch-platform.plan.md) (Phase 3 scope)
- Related skills: [`vmc-autoresearch-core`](../vmc-autoresearch-core/SKILL.md) (spine), [`autonomous-verifier`](../autonomous-verifier/SKILL.md), [`vmc-autopilot-oneshot`](../vmc-autopilot-oneshot/SKILL.md)
