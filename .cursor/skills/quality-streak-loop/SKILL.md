---
name: quality-streak-loop
description: Realistic product-testing loop that requires N consecutive passing scenarios under a fixed quality bar and turns every failure into durable regression + benchmark coverage before resetting the streak to zero. Runs realistic cases one at a time under consistent conditions; on any failure it documents the case, adds a regression test and benchmark, fixes the root cause, verifies, and restarts the streak. Stops only after N successes in a row at the original bar. Use when quality needs a strict consecutive-success gate and failures should permanently strengthen the suite — e.g. "quality streak loop", "N passing scenarios in a row", "harden until it survives realistic testing", "soak test until stable".
---

# Quality Streak Loop

A realistic product-testing workflow that turns every failure into **permanent**
regression coverage and restarts the success streak after each fix. The bar is a
strict run of `N` consecutive passing scenarios — one isolated success never
counts; the streak does.

Restarting the streak on every failure is what prevents intermittent weakness from
hiding behind a few lucky passes. Converting each failure into durable coverage is
what makes the suite stronger after every miss.

## The invariant (read this first)

1. **Streak, not single passes.** Stop only after `N` consecutive passes at the
   bar. Any failure resets the streak to **zero**.
2. **Every failure becomes durable coverage.** A failure is not "fixed" until a
   regression test + benchmark captures it so it can never silently return.
3. **Never lower the bar to keep the streak.** Do not skip hard cases, weaken
   assertions, or soften the quality bar to preserve a run.
4. **Representative scenarios.** The case distribution must reflect real usage, not
   a cherry-picked easy set.

## When to Use

- Quality needs a strict consecutive-success gate before shipping/promoting.
- You want every failure to permanently improve the test + benchmark suite.
- The user says "quality streak loop", "N in a row", "soak/harden until stable", or
  "keep testing realistic scenarios until it stops breaking".

## When NOT to Use

- A single failing test with a known fix (just fix it + add the regression test).
- Pure latency/throughput goals — use [perf-budget-loop](../perf-budget-loop/SKILL.md).
- Search/optimization of a scoreable artifact — use
  [champion-challenger-loop](../champion-challenger-loop/SKILL.md).

## Parameters to define BEFORE starting

```yaml
scenarios:     <how realistic cases are drawn; the representative distribution>
quality_bar:   <what counts as a pass; the exact assertions/criteria>
N:             <required consecutive successes>     # choose BEFORE the run
conditions:    <consistent run environment, seeds, fixtures>
evidence:      <what proof a pass/fail requires (logs, snapshots, metrics)>
```

`N` and the bar are fixed at the start. Changing either mid-run invalidates the
streak.

## The loop

```text
pin (scenarios, quality_bar, N, conditions, evidence)
streak = 0
while streak < N:
    case   = draw the next realistic scenario (representative)
    result = run(case) under fixed conditions ; preserve evidence
    if result passes the quality_bar:
        streak += 1
        record the pass + evidence
    else:                                  # FAILURE -> permanent improvement
        document(case, observed vs expected)
        add_regression_test(case)          # failing-test-first (see reliable-tdd-loop)
        add_benchmark_coverage(case)       # so it's measured forever after
        fix_root_cause()                   # minimal, scoped
        verify(case passes + regression test green + no new breakage)
        streak = 0                         # RESET — the run starts over
return when streak == N consecutive passes at the original bar
```

## What "turn the failure into coverage" means

A failure is only closed when all are true:

- A **regression test** reproduces the failure (red) then passes after the fix
  (green) — drive this with [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md).
- A **benchmark/scenario** is added so the case is part of future runs, not a
  one-off manual check.
- The **root cause** is fixed (not the symptom), scoped to the defect.
- The fix introduces **no new failures** in the existing suite.

Skipping the regression-coverage step is the most common way this loop fails to
actually improve quality — it just becomes manual retesting.

## Per-stack backends (delegate, do not reinvent)

| Stack | Scenario harness | Regression coverage home | Delegate to |
|---|---|---|---|
| VMC (agentic-swarm) | domain contract evals, dispatch scenarios, Playwright flows | `<domain>-contracts.test.ts`, e2e specs | [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md), [autonomous-verifier](../autonomous-verifier/SKILL.md) |
| Trading Lab | realistic backtests/walk-forwards | trading guardrail + simulator tests | trading test set; `golden-verify`, `leakage-audit` |
| plx-customer-portal | realistic user/admin flows | Vitest `__tests__`, e2e | repo test suite (staging) |
| Generic repo | representative end-to-end scenarios | that repo's test + bench suite | [project-hardener](../project-hardener/SKILL.md) |

Repo-specific commands and the scenario catalog live in [reference.md](reference.md).

## Hard-stop conditions

```yaml
stop_if:
  bar_lowered_to_preserve_streak: true   # contract violation
  failure_fixed_without_regression_test: true
  scenario_distribution_unrepresentative: true
  N_not_fixed_before_run: true
  same_failure_recurs_after_claimed_fix: true   # root cause not actually fixed
```

Hard-stop shape: `stop_reason`, `loop: quality-streak`, `attempt`,
`failed_checks[]`, `evidence_paths[]`, `next_action` (per `orchestration-kernel` §5).

## Completion contract

Do not report done until all are true:

- `N` consecutive passes recorded at the **original** bar, each with evidence.
- Every failure encountered during the run has a committed regression test +
  benchmark, with red→green evidence.
- No assertion was weakened and no hard scenario was skipped to keep the streak.
- The final streak ran under the same pinned conditions as the rest.

## Additional resources

- Scenario catalogs, per-repo commands, worked example: [reference.md](reference.md)
- Shared contracts (evidence bundle, hard-stop): [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Failing-test-first engine: [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md)
- Convergence sibling: [project-hardener](../project-hardener/SKILL.md)
