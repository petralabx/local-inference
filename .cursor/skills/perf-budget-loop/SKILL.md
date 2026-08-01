---
name: perf-budget-loop
description: Performance optimization loop that drives every route/surface under a named latency budget using one repeatable benchmark. Pins the exact metric, route set, environment, warm-up, and run count; captures a baseline for every target before changes; then makes one optimization at a time and re-measures ALL routes to catch local wins that regress another route. Continues until every target meets the budget under the original conditions. Use when a product has a defined route set, a stable perf harness, and a latency target that maps to a specific metric and environment — e.g. "sub-50ms page-load loop", "get every page under <budget>", "performance budget loop", "optimize load time across all routes".
---

# Performance Budget Loop

A performance optimization workflow that uses **one repeatable benchmark** and
stops only when **every** target surface meets a named budget. It generalizes the
"sub-50 ms page-load loop": the 50 ms is just one instance of a configurable
`(metric, budget, environment)`.

The discipline that makes it work: a fixed harness (no anecdotal tuning) and
re-measuring **all** routes after each change (so a local win that quietly slows
another route is caught immediately).

## The invariant (read this first)

1. **One harness, fixed conditions.** Same metric, routes, environment, warm-up,
   and run count for every measurement in the run. Change the harness → restart.
2. **Measure every route after every change.** A change is not "good" because the
   route you touched got faster; it is good only if no other route regressed.
3. **Name the metric and hardware.** "Page load" is ambiguous (server response vs
   render-complete vs a browser timing metric). Pin it so the budget is reproducible.
4. **Budget is the stop condition.** Continue until *every* target meets it — not
   until the slowest one you happened to look at improves.

## When to Use

- A defined set of routes/surfaces/endpoints with a stable, scriptable benchmark.
- A latency target that maps to a specific metric and environment.
- The user says "get every page under N ms", "perf budget loop", "sub-50ms loop",
  or "optimize load/latency across all routes until they all pass".

## When NOT to Use

- No repeatable harness yet — build and pin the harness first, or the loop just
  produces anecdotes.
- A single known hotspot with an obvious fix (just fix it; this loop is for driving
  a whole surface set under budget).
- Correctness/quality regressions are the real concern — use
  [quality-streak-loop](../quality-streak-loop/SKILL.md).

## Parameters to define BEFORE starting

```yaml
metric:        <exact metric, e.g. server TTFB | render-complete | LCP | p95 route latency>
budget:        <threshold, e.g. 50ms>   # the target every route must meet
routes:        [ <every target route/surface/endpoint> ]
environment:   <hardware + build mode, e.g. "prod build, c4.8xlarge, cold cache">
warmup:        <warm-up behavior before timed runs>
runs:          <N benchmark runs per route; report which statistic — median/p95>
statistic:     <median | p95 | max>      # which run statistic is compared to budget
```

Write these into the bundle. If any of them change mid-run, the prior
measurements are no longer comparable — restart the baseline.

## The loop

```text
pin (metric, budget, routes, environment, warmup, runs, statistic)
baseline = measure(every route)            # capture before any change
record baseline for ALL routes in the bundle
while any route's statistic > budget:
    target  = worst offending route (or highest-leverage hotspot)
    change  = ONE significant optimization addressing it
    apply(change)
    results = measure(EVERY route)         # not just the one you changed
    if any route regressed past budget that previously passed:
        treat as a regression: revert or fix before proceeding
    record results + delta vs baseline for all routes
return when every route's statistic <= budget under the original conditions
```

## Regression rule (the part people skip)

After each change, compare **all** routes to the baseline, not just the target:

- A route that *passed* and now *fails* the budget is a hard regression → revert
  the change or fix the regression before continuing.
- A route that got slower but still passes is logged as a watch item.
- Only count progress when the global picture improves.

## Per-stack backends (delegate, do not reinvent)

| Stack | Harness | Metric examples | Delegate to |
|---|---|---|---|
| VMC (Next.js, agentic-swarm) | Lighthouse CI / Playwright timing on the route list | LCP, TTFB, route p95 | QA `performance-load-testing` skill; [autonomous-verifier](../autonomous-verifier/SKILL.md) |
| plx-customer-portal (Next.js) | Lighthouse CI / k6 against `staging` | LCP, server TTFB | same; staging-only |
| API services | k6 / Locust against the endpoint set | p50/p95 latency, throughput | QA `performance-load-testing` skill |

Repo-specific harness commands, route lists, and the exact metric definition live
in [reference.md](reference.md) — keep `SKILL.md` portable.

## Hard-stop conditions

```yaml
stop_if:
  harness_not_repeatable: true          # results vary run-to-run beyond noise
  metric_or_environment_unpinned: true  # budget is not reproducible
  changed_conditions_mid_run: true      # baseline no longer comparable
  budget_physically_unreachable: true   # report best achievable + evidence, escalate
```

Hard-stop shape: `stop_reason`, `loop: perf-budget`, `attempt`, `failed_checks[]`,
`evidence_paths[]`, `next_action` (per `orchestration-kernel` §5).

## Completion contract

Do not report done until all are true:

- Every target route meets `budget` on `metric` under the pinned `environment`,
  with the benchmark output recorded per route.
- The final measurement used the **same** harness/conditions as the baseline.
- No route that previously passed is left regressed below budget.
- If the budget is not reachable for some route, say so plainly with the best
  achieved number and the bottleneck evidence — do not quietly drop the route.

## Additional resources

- Repo harness commands, route lists, metric definitions, worked example: [reference.md](reference.md)
- Shared contracts (evidence bundle, hard-stop): [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Verification discipline: [autonomous-verifier](../autonomous-verifier/SKILL.md)
- Quality (correctness) sibling loop: [quality-streak-loop](../quality-streak-loop/SKILL.md)
