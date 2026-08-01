# champion-challenger-loop — reference

Repo-specific backends for the universal loop in [SKILL.md](SKILL.md). The
`SKILL.md` body is portable; everything that names a path, command, or schema
lives here.

## 1. Picking the gate and guards per stack

The loop is only as honest as its gate. Use the most trustworthy held-out
evidence the repo already maintains. Do not invent a new gate when one exists.

### agentic-swarm / VMC (verified 2026-06-19)

- **Champion store:** the current prompt/policy/config under version control is the
  champion genome; record its gate score in the run bundle.
- **Working signal:** a cheap eval over a reusable dev slice (a subset of the
  domain contract eval, or a scored dispatch sample).
- **Gate:** the Postgres-backed holdout eval set wired by `vmc-autoresearch-core`.
  Scaffold it with `.cursor/skills/vmc-autoresearch-core/scripts/init-eval.sh`
  (emits an `eval/` template: `baseline.json`, `ownership.json`, `harness.ts`).
  Never select gate rows that were used to propose or tune a challenger.
- **Guards (`[safety]`):** pillar checks; the null-hypothesis variance arm
  (promotion requires `|z| >= 1.0` on the target pillar — see
  [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md)); and the repo commit/push
  gate `./scripts/wterm-preflight.sh --mode pre-push`
  (see [wterm-preflight](../wterm-preflight/SKILL.md)).
- **Delegate the mechanics to:** [vmc-autoresearch-core](../vmc-autoresearch-core/SKILL.md)
  (baseline-freeze + holdout) and
  [parallel-multiagent-orchestrator](../parallel-multiagent-orchestrator/SKILL.md)
  (best-of-N challengers per cycle on isolated worktrees).

### Trading Lab v2 (verified paths 2026-06-19)

- **Gate:** the frozen refs under `eval/trdv2-discovery-loop/` — `baseline.json`
  (the calibrated DSR gate), `holdout.ref.json`, plus the shared `harness.ts` and
  role-routing `models.json`. The **holdout window 2026-03-06 → 2026-06-05** is
  hook-enforced and must never be read while editing — it is the canonical "fresh
  examples you did not inspect". Do not weaken it.
- **Guards:** [golden-verify](../../../.claude/skills/golden-verify/SKILL.md)
  (frozen-ref sha256 integrity) and
  [leakage-audit](../../../.claude/skills/leakage-audit/SKILL.md)
  (look-ahead / purge-embargo) MUST pass before any promotion.
- **Registration:** every challenger is an experiment — register it BEFORE running
  via [register-experiment](../../../.claude/skills/register-experiment/SKILL.md)
  (appends to `research/experiments.jsonl` + `EXPERIMENTS.md`).
- **Minimum margin:** use the program's calibrated DSR/gate thresholds, not an
  ad-hoc number.

### plx-customer-portal (verified 2026-06-19)

This repo has **no holdout/eval infrastructure**, so the loop must construct its own
fresh gate. Target the `staging` branch only (never `master` without approval).

- **Champion store:** the artifact under change (a prompt, a route config, a ranking
  heuristic) on the `staging` branch.
- **Gate:** cut a fresh eval split the editor never sees (hold back N cases or use a
  time-based split) and record the split id in the bundle.
- **Working signal:** the remaining (tunable) cases or a cheap proxy metric.
- **Guards (`[safety]`):** run from `portal/` —
  `npm run typecheck && npm run lint && npm run test` (Vitest, `vitest run`) and
  `npm run audit:hygiene` (`scripts/audit-module-coverage.sh`). Any DB-touching
  challenger must first pass `bash scripts/assert-staging-context.sh` so it cannot
  point at the production database.

### Other generic repos (clawdbot, mrp, etc.)

- **Gate:** cut a fresh eval split the editor never sees; store the split id.
- **Working signal:** the remaining (tunable) cases or a cheap proxy metric.
- **Guards:** that repo's own gates — clawdbot `pnpm build && pnpm lint && pnpm test`;
  mrp `npm install && npm test`. Self-locate the repo root rather than hardcoding paths.

## 2. Goodhart / easy-win checklist

Before accepting a promotion that looks "too good", confirm none of these:

- Gate examples overlap the editing/working set (leakage).
- A guard was loosened, skipped, or its threshold lowered since the last failure.
- The metric improved but a guard you stopped checking silently regressed.
- The win does not reproduce on a second, independently drawn fresh slice.
- The challenger special-cases the known gate examples (memorization).

If any are true: reject, restore the guard, re-cut the gate, and log it.

## 3. Evidence bundle layout

Reuse the `orchestration-kernel` evidence shape:

```text
.orchestrator/champion-<slug>/
├── PARAMS.md            # N, minimum_margin, working_signal, gate id, [safety]
├── champion.json        # current genome + gate_score + working_score
├── attempt_log.jsonl    # one line per cycle: genome, scores, verdict, reason
├── cycles/<k>/          # per-cycle diffs, command logs, gate output
└── REPORT.md            # final champion, why, budget spent, honest outcome
```

## 4. Worked example (prompt optimization, generic stack)

```text
PARAMS: N=8, minimum_margin=+2 pts, working=dev-50, gate=holdout-30 (unseen), guards=[lint, schema, refusal-rate<=baseline]
champion: prompt_v0, gate_score=71
cycle 1: failure="verbose on edge cases" -> challenger adds terseness rule
         working 64->69 (better) -> freeze -> gate 71->72 (Δ+1 < margin) -> reject:gate (keep v0)
cycle 2: failure="misses unit in answers" -> challenger adds unit instruction
         working 69->74 -> freeze -> gate 71->75 (Δ+4 >= margin), guards ok
         easy-win check: re-verify on holdout-30b -> holds (74) -> ACCEPT (champion=prompt_v2, 75)
...
cycle 8: budget 0 -> return champion=prompt_v5 (gate 79), report log
```

The promotion in cycle 2 only counts because gate examples were never used to
write the terseness/unit rules, the margin was real, the guards held, and the win
reproduced on a second fresh slice.
