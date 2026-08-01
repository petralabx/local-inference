# Parallel Multiagent Orchestrator — Reference

Full spawn matrix, REPORT.md schema, scoring math, and auto-escalation log format. Load on demand from [SKILL.md](SKILL.md).

## 1. Spawn Matrix + Commands

### 1.1 Inputs

| Input | Path | Produced by |
|---|---|---|
| Hypotheses | `research/loop-<N>/hypotheses.md` | Frontier hypothesis generator (loop start) |
| Ownership manifest | `eval/ownership.json` | Loop 0 (`vmc-autoresearch-core`) |
| Model pinning | `eval/models.json` | Loop 0 (`vmc-autoresearch-core`) |
| Baseline metrics | `eval/baseline.json` | Loop 1 (`vmc-autoresearch-core`) |
| Scorecard floors | `eval/scorecard.md` | Loop 1 (`vmc-autoresearch-core`) |

### 1.2 Per-hypothesis spawn

For each `H<M>` with tag `T<M>` in `hypotheses.md`:

```bash
# Derive executor from eval/models.json
EXECUTOR=$(jq -r ".executor_by_tag.\"$T\"" eval/models.json)
if [ "$DOMAIN" = "swarm" ] && [ "$T" != "mechanical" ]; then
  EXECUTOR=$(jq -r '.swarm_default_executor' eval/models.json)
fi

# Create branch
git checkout -b "autoresearch/$DOMAIN/loop-$N/hyp-$M" "autoresearch/$DOMAIN/loop-$N"

# Spawn one best-of-n-runner
# (see Task tool; prompt template in SKILL.md §1 Spawn template)
```

### 1.3 Spawn-prompt contract

Every `best-of-n-runner` prompt **must** include these clauses verbatim (paraphrased is insufficient — the orchestrator checks for them before scoring):

1. `Scope: eval/ownership.json (owns + consumes_readonly only).`
2. `Forbidden: any file matching eval/ownership.json .forbidden.`
3. `Do own vmc_checkout_task for todoId=ar-<domain>-l<N>-h<M> before first edit.`
4. `Do NOT run eval/harness.ts --mode=score yourself; the orchestrator scores.`
5. `Do NOT merge; produce the diff only.`
6. `Stop after 4 failed attempts and write research/loop-<N>/hyp-<M>/BLOCKER.md.`

### 1.4 Parallelism budget

| Loop | Default N | Diversity arm | Max |
|---|---|---|---|
| Loop 2 | 2 | disabled | 3 |
| Loop 3 | 2 | enabled (for non-`deep`) | 4 |
| Loop 4 | 2 | enabled (for non-`deep`) | 4 |

Raise only after a budget review against per-domain caps in plan Resolved Decision #1 ($200 todos, $300 chat, $300 second-brain, $500 swarm).

## 2. Scope-Lock Enforcement

### 2.1 Script contract

`.cursor/hooks/scope-lock.sh <domain> <patch-path>`:

- Exit 0: patch is in-scope; candidate eligible for scoring.
- Exit 2: `SCOPE_LOCK_VIOLATION forbidden:<path>` — patch touches a file in `.forbidden`. Reject + archive.
- Exit 3: `SCOPE_LOCK_VIOLATION not_owned:<path>` — patch touches a file outside `.owns`. Reject + archive.
- Exit 64/66: input error (missing patch, missing manifest); block and fix tooling.

A copy of the canonical script ships at [`scripts/scope-lock.sh`](scripts/scope-lock.sh) for skills-mode smoke testing. In a real domain worktree, prefer `.cursor/hooks/scope-lock.sh`.

### 2.2 Rejection archive shape

```
research/loop-<N>/rejected/hyp-<M>/
├── patch.diff                 # the rejected patch
├── reason.txt                 # exit line from scope-lock.sh
└── NOTES.md                   # forwarded from the subagent
```

Rejected candidates are never scored; they still appear in REPORT.md's per-tag win-rate block as `attempts++`.

## 3. REPORT.md Schema

Every `research/loop-<N>/REPORT.md` must include this frontmatter + body shape:

```markdown
---
domain: <domain>
loop: <N>
generated_at: <ISO timestamp>
orchestrator_version: parallel-multiagent-orchestrator@1.0.0
parent_todo_id: ar-<domain>-l<N>
winner: hyp-<M> | none
loop_score: <value>
pass_threshold: <value>           # from eval/scorecard.md
stagnant: <true|false>
auto_escalations: <count>
---

# Loop <N> Report — <domain>

## Candidates

| Hyp | Tag | Executor | Branch | Status | loop_score |
|---|---|---|---|---|---|
| H01 | mechanical | composer-2-fast | autoresearch/<d>/loop-<N>/hyp-01 | winner | 3.2 |
| H02 | deep | claude-opus-4-7-thinking-high | autoresearch/<d>/loop-<N>/hyp-02 | rejected-scope | n/a |

## Scorecard Summary

(Pillar deltas vs baseline, in null-hypothesis-variance units.)

## Null-Hypothesis Control Arm

- Re-run baseline variance: <value>
- Threshold for "improvement": > 1.0 variance units

## Cross-Domain Regression Check

- chat-contracts:          pass
- todos-contracts:         pass
- second-brain-contracts:  pass
- swarm-contracts:         pass

## Auto-Escalations

(Empty if none; otherwise one entry per re-tag decision.)

## Win Rate By Tag

```yaml
win_rate_by_tag:
  mechanical: { attempts: 1, winners: 1, rate: 1.0 }
  moderate:   { attempts: 0, winners: 0, rate: 0.0 }
  deep:       { attempts: 1, winners: 0, rate: 0.0 }
executor_win_rate:
  composer-2-fast:               { attempts: 1, winners: 1 }
  claude-opus-4-7-thinking-high: { attempts: 1, winners: 0 }
  gpt-5.3-codex-high-fast:       { attempts: 0, winners: 0 }
```

## Risk Notes

(Reviewer fills.)

## Next Loop Seeds

(Carry-forward hypotheses if winner was stagnant or a close runner-up exists.)
```

## 4. Scoring Math

Per-pillar improvement, in null-hypothesis-variance units:

```
pillar_improvement = (candidate_metric - baseline_metric) / null_hypothesis_variance
```

Sign convention: for pillars where **lower is better** (e.g. latency), flip the sign so improvement is always positive when the candidate is better. Declare sign per pillar in `eval/scorecard.md`.

Aggregate:

```
loop_score =  sum(pillar_improvement for each pillar)
           - 10 * count(cross_domain_regressions)
           - 100 * any_holdout_leak
           - 5  * count(scope_lock_violations)
```

Winner selection:

1. Filter to candidates passing Step A gate filters.
2. Among remaining, max `loop_score`.
3. If `max(loop_score) < pass_threshold` → stagnant loop, no winner declared.
4. Tie-break: prefer candidate with **smaller** patch footprint (lines changed), then prefer frontier-executor over composer (interpreted as "more likely to generalize").

See also [`vmc-autoresearch-core/reference.md §5`](../vmc-autoresearch-core/reference.md#5-scoring-math).

## 5. Auto-Escalation Log Format

When a composer-executed candidate fails the loop gate twice on the same hypothesis line, record in `research/loop-<N>/REPORT.md` under `## Auto-Escalations`:

```yaml
- hypothesis: H<M>
  original_tag: moderate
  original_executor: composer-2-fast
  failures:
    - loop: 02
      failure_reason: "below null-hypothesis variance on pillar X"
    - loop: 03
      failure_reason: "scope-lock violation: touched portal/src/lib/vmc/core"
  escalated_at: <ISO timestamp>
  new_tag: deep
  new_executor: claude-opus-4-7-thinking-high
  eval_models_json_note: "auto-escalated after 2 failures; see loop-03/REPORT.md"
```

Then mutate `eval/models.json` **only** by adding a per-hypothesis override entry (never re-pin the global tag table mid-project):

```json
{
  "executor_by_tag": { "mechanical": "composer-2-fast", ... },
  "per_hypothesis_overrides": {
    "l03-h02": { "executor": "claude-opus-4-7-thinking-high", "reason": "auto-escalated" }
  }
}
```

## 6. Mock Loop (Exit-Criteria Smoke Test)

The skill ships a self-contained mock loop at [`scripts/mock-loop.sh`](scripts/mock-loop.sh) that:

1. Creates a temp `eval/ownership.json` with well-defined `owns` and `forbidden` globs.
2. Synthesizes **2** candidate diffs: one in-scope (`hyp-01`), one out-of-scope (`hyp-02`, touches a `forbidden` path).
3. Runs `scripts/scope-lock.sh` against each: `hyp-01` passes, `hyp-02` is rejected with exit 2.
4. Emits mock scorecards (`scorecard-hyp-01.json`, `scorecard-hyp-02.json`, `scorecard-null.json`) with deterministic numbers.
5. Runs `scripts/pick-winner.sh` to produce `research/loop-99/REPORT.md` declaring `hyp-01` the winner and recording `hyp-02` as `rejected-scope`.

Used as a regression test of the skill itself. See [examples.md §C](examples.md#c-skill-regression--mock-loop).

## 7. Related Documents

- Parent plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](.cursor/plans/vmc-autoresearch-platform.plan.md) (Phase 3 scope)
- Spine skill: [`vmc-autoresearch-core/SKILL.md`](../vmc-autoresearch-core/SKILL.md)
- Verifier: [`autonomous-verifier/SKILL.md`](../autonomous-verifier/SKILL.md)
- Scope-lock canonical hook: [`.cursor/hooks/scope-lock.sh`](../../hooks/scope-lock.sh) (per-project, created during Phase 0 pilot)
- Rules: [`reliability-verification.mdc`](../../rules/reliability-verification.mdc), [`agent-testing-contract.mdc`](../../rules/agent-testing-contract.mdc), [`surgical-changes.mdc`](../../rules/surgical-changes.mdc)
