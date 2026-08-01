# perf-budget-loop — reference

Repo-specific harness wiring for the universal loop in [SKILL.md](SKILL.md). Keep
`SKILL.md` portable; commands, route lists, and metric definitions live here.

## 1. Choosing and naming the metric

"Page load" is three different numbers. Pick one and write it into `PARAMS.md`:

- **server TTFB** — time to first byte from the server (excludes client render).
- **render-complete / LCP** — browser-side largest-contentful-paint or full render.
- **route p95 latency** — server-side request latency percentile for an endpoint.

The budget is only meaningful with the metric **and** the hardware/build mode
pinned (e.g. "LCP, prod build, warm cache, median of 5 runs on the prod EC2").

## 2. Per-stack harness (verify before trusting)

### agentic-swarm / VMC (Next.js, `apps/vmc-web`)

- **Routes:** enumerate the target `/vmc/*` routes explicitly (don't say "all
  pages"). Keep the list in `PARAMS.md`.
- **Harness:** Lighthouse CI for render metrics, or Playwright navigation timing
  for scripted route timing. Delegate the harness mechanics to the QA
  `performance-load-testing` skill (Lighthouse CI / k6 / py-spy).
- **Environment:** run against a production build (`npm run build && npm start`),
  not `next dev` — dev-mode timings are not representative.
- **Guard:** before/after, run the repo gate `./scripts/wterm-preflight.sh --mode
  pre-push` so a perf change doesn't break tests/types.

### plx-customer-portal (Next.js, `portal/`)

- **Environment:** `staging` only (per repo policy). Production-build timings.
- **Harness:** Lighthouse CI against the staging URL, or k6 for endpoint latency.
- **Guard:** from `portal/`, `npm run typecheck && npm run lint && npm run test`.

### API services

- **Harness:** k6 or Locust against the endpoint set; report p50 and p95.
- **Warm-up:** discard the first batch of requests; pin connection reuse settings.

## 3. Repeatability checklist (do this before the baseline)

Run the harness twice with no code change. If the chosen statistic varies beyond a
small noise band, the harness is not repeatable — fix that first (pin CPU governor,
warm caches, fixed run count, isolate the box) before any optimization. A
non-repeatable harness turns the whole loop into anecdotes.

## 4. Evidence bundle layout

```text
.orchestrator/perf-<slug>/
├── PARAMS.md            # metric, budget, routes, environment, warmup, runs, statistic
├── baseline.json        # per-route statistic before any change
├── rounds/<k>/
│   ├── change.diff
│   └── results.json     # per-route statistic after the change + delta vs baseline
└── REPORT.md            # final per-route table vs budget + any unreachable routes
```

## 5. Worked example (VMC, LCP budget)

```text
PARAMS: metric=LCP, budget=50ms? -> unrealistic for full render; use 1200ms for LCP
        OR metric=server-TTFB, budget=50ms (realistic server target)
routes=[/vmc/today, /vmc/projects, /vmc/trading-lab], env="prod build, vmc-prod EC2",
warmup="1 throwaway nav", runs=5, statistic=median

baseline(TTFB ms): today=88, projects=140, trading-lab=210   (all > 50, fail)
round 1: add route segment caching on /vmc/projects
         measure ALL -> today=86, projects=44 (pass), trading-lab=205  (no regressions) ok
round 2: stream trading-lab shell + defer heavy widget
         measure ALL -> today=85, projects=45, trading-lab=47 (pass)
         check: did any passing route regress? projects 44->45 still passes -> ok
round 3: today still 85 > 50 -> add edge cache for /vmc/today
         measure ALL -> today=41, projects=46, trading-lab=48  -> ALL <= 50
return: every route median TTFB <= 50ms under the pinned conditions
```

Note how each round re-measured **every** route — that is what catches a fix to one
page that adds shared-bundle weight slowing another.
