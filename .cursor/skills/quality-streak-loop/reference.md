# quality-streak-loop — reference

Repo-specific wiring for the universal loop in [SKILL.md](SKILL.md). Keep
`SKILL.md` portable; scenario catalogs and commands live here.

## 1. Choosing N and the scenario distribution

- **Pick `N` before the run** and write it into `PARAMS.md`. Typical: 10–25 for a
  feature gate; higher for reliability-critical surfaces. Larger `N` exponentially
  lowers the chance an intermittent bug slips through.
- **Representative distribution:** weight scenarios by real usage. Include the
  boring-but-common path, the known edge cases, and at least one adversarial case.
  A streak built only on happy-path cases proves little.

## 2. Per-stack scenario harness + regression home (verify before trusting)

### agentic-swarm / VMC

- **Scenarios:** domain contract evals, scored dispatch scenarios, and Playwright
  end-to-end flows for `/vmc/*`.
- **Regression home:** per-domain `<domain>-contracts.test.ts` (drive new ones via
  [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md)) and e2e specs. Do NOT dump
  regressions into the catch-all `reliability-contracts.test.ts`.
- **Verify/gate:** `./scripts/wterm-preflight.sh --mode pre-push` plus the relevant
  contract suites. Use [autonomous-verifier](../autonomous-verifier/SKILL.md) for
  the per-case verification matrix.

### Trading Lab v2

- **Scenarios:** realistic backtests / walk-forwards over representative
  symbol/timeframe slices (respect the hook-enforced holdout window).
- **Regression home:** `tests/test_trading_guardrails.py`,
  `tests/test_simulator_realism.py`, `tests/test_walk_forward_safety.py`.
- **Guards:** `golden-verify` (frozen-ref integrity) and `leakage-audit` must pass;
  a "fix" that touches frozen refs is a hard stop.

### plx-customer-portal (`portal/`, staging only)

- **Scenarios:** realistic customer + admin flows (onboarding, document, forms).
- **Regression home:** Vitest under `portal/src/__tests__` (+ any e2e).
- **Verify/gate:** `npm run typecheck && npm run lint && npm run test`; DB-touching
  cases require `bash scripts/assert-staging-context.sh` first.

### Generic repo

- Use the repo's own test + benchmark suite; delegate convergence to
  [project-hardener](../project-hardener/SKILL.md).

## 3. Evidence bundle layout

```text
.orchestrator/streak-<slug>/
├── PARAMS.md            # scenarios, quality_bar, N, conditions, evidence policy
├── streak_log.jsonl     # one line per case: scenario, pass|fail, streak_after, evidence path
├── failures/<k>/
│   ├── repro.md         # observed vs expected
│   ├── regression.diff  # the added test + benchmark
│   └── fix.diff         # the scoped root-cause fix
└── REPORT.md            # final N-in-a-row evidence + every failure's coverage
```

## 4. Worked example (VMC dispatch reliability)

```text
PARAMS: scenarios="weighted dispatch cases (happy 60%, edge 30%, adversarial 10%)",
        quality_bar="correct route + no stale todo + callback success", N=15,
        conditions="seeded, memory checkpointer", evidence="dispatch log + counters"

case 1..6  pass -> streak=6
case 7     FAIL: callback lost on retry
           -> document; add swarm-contracts regression test (red); fix retry path (green);
              add benchmark to dispatch scenario set; verify no new breakage
           -> streak=0  (RESET)
case 1..15 pass (including the new regression case) -> streak=15 -> DONE
```

The failure at case 7 permanently added a callback-retry regression test and a
benchmark; the run then had to reach 15 clean passes from zero, with that new case
now part of the distribution.

## 5. Anti-patterns that void the run

- Lowering an assertion or marking a hard case `skip` to keep the streak alive.
- "Fixing" by catching/swallowing the error instead of the root cause (the same
  failure recurs → hard stop `same_failure_recurs_after_claimed_fix`).
- Counting a pass without the required evidence captured.
- Drawing only easy scenarios so the distribution stops being representative.
