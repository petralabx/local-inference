# ui-ux-design-loop — Reference

Reference cookbook for the [SKILL.md](SKILL.md) gate pack.

The skill is adapter-driven: repo-specific wiring lives in `ui-loop.config.json`
(or `UI_LOOP_CONFIG`) and is read by
`.cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs`.

## Manifest schema (all keys)

| Key | Type | Purpose |
|---|---|---|
| `appDir` | string | App directory where Playwright/lint/typecheck commands run |
| `tokenCheck.command` | string | Token checker executable for G1 |
| `tokenCheck.args` | string[] | Static args for the checker command |
| `tokenCheck.fileGlobs` | string[] | Candidate file globs scanned for design-token drift |
| `componentMap` | string[] | Shared component hints for G1 component-usage checks |
| `routesGlob` | string | Glob for route modules consumed by G2/G4 fixtures |
| `renderGuard.authHeading` | string | Heading text identifying auth-wall render |
| `renderGuard.errorHeading` | string | Heading text identifying error-boundary render |
| `a11yAllowlist` | string | Route-keyed allowlist file for known axe rule IDs |
| `viewports` | string[] | Default Playwright project matrix for G3 |
| `baseUrlEnv` | string | Env var read by Playwright for target base URL |
| `authBypassEnv` | string | Env var enabling local auth bypass preview mode |
| `previewCommand` | string | Preview boot command used by the adapter |

## VMC reference adapter (worked example)

Current repository adapter (`ui-loop.config.json`):

```json
{
  "appDir": "apps/vmc-web",
  "tokenCheck": {
    "command": "python3",
    "args": ["scripts/check-vmc-theme-tokens.py"],
    "fileGlobs": ["apps/vmc-web/src/*.ts", "apps/vmc-web/src/*.tsx"]
  },
  "componentMap": ["ActionButton", "PageHeader", "vmc-pill"],
  "routesGlob": "apps/vmc-web/e2e/helpers/ui-loop/*.routes.ts",
  "renderGuard": {
    "authHeading": "Sign in with Microsoft Entra ID",
    "errorHeading": "Something went wrong"
  },
  "a11yAllowlist": "apps/vmc-web/e2e/ui-a11y-allowlist.json",
  "viewports": ["chromium", "tablet", "mobile-chrome"],
  "baseUrlEnv": "E2E_BASE_URL",
  "authBypassEnv": "VMC_LOCAL_AUTH_BYPASS",
  "previewCommand": "npm run dev"
}
```

## Gate command cookbook (adapter-parameterized)

All E2E gates need a local preview. Either let Playwright boot one, or point to an
already-running server by exporting the adapter's `baseUrlEnv`.

> **Cleanup gotcha:** a local `next dev` preview emits route types under
> `<appDir>/.next/dev/types/**`. A later `tsc --noEmit` (the pre-push gate)
> picks those up and can fail on generated dev-only route types. After running a
> preview, `rm -rf <appDir>/.next/dev` and restore `<appDir>/next-env.d.ts`
> before typecheck / pre-push.

### G1 — design-system conformance

```bash
# loop-scoped: zero NEW raw-color findings in changed files (blocks)
.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --base origin/main
.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --staged
.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --files "<adapter.tokenCheck.fileGlobs candidate>"
.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --strict-components
.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --selftest
```

- Hard fail: new raw `oklch/rgb/rgba/hex` or fixed palette classes in loop-scoped diff.
- Advisory/hard (toggle): raw platform controls when shared primitives should be used.
- G1 behavior is controlled by adapter token checker command + globs.

### G2 — interaction wiring

```bash
cd <adapter.appDir>
<adapter.authBypassEnv>=1 UI_WIRING_STRICT=1 npx playwright test e2e/ui-wiring-sweep.spec.ts --project=chromium
# higher-signal, opt-in dynamic pass:
<adapter.authBypassEnv>=1 UI_WIRING_STRICT=1 UI_WIRING_DYNAMIC=1 npx playwright test e2e/ui-wiring-sweep.spec.ts --project=chromium
# focused route subset:
UI_LOOP_ROUTE_FILTER="stage-,bloomberg" <adapter.authBypassEnv>=1 npx playwright test e2e/ui-wiring-sweep.spec.ts --project=chromium
```

- Static pass flags: dead links and unlabeled controls.
- Dynamic pass flags controls with no observable effect. Tune noisy surfaces with
  `UI_WIRING_ACTION_TIMEOUT_MS` (default `750`) and `UI_WIRING_OBSERVE_MS`
  (default `100`) instead of letting locator calls consume the full test timeout.
- Mark truly inert controls with `data-ui-inert`, `disabled`, or `aria-disabled`.

### G3 — responsive matrix

```bash
.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh
.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh --include-safari
.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh --spec e2e/ui-a11y.spec.ts
.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh --update-snapshots
.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh --projects "tablet"
UI_STAGE_RAIL_VISUAL=1 .cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh --spec e2e/ui-stage-rail-visual.spec.ts --update-snapshots
```

- Defaults come from adapter keys: `viewports`, `appDir`, and `baseUrlEnv`.
- Manual `--projects` overrides still work for focused runs.

### G4 — accessibility

```bash
cd <adapter.appDir>
<adapter.authBypassEnv>=1 UI_A11Y_STRICT=1 npx playwright test e2e/ui-a11y.spec.ts --project=chromium --project=tablet --project=mobile-chrome
UI_LOOP_ROUTE_FILTER="stage-" <adapter.authBypassEnv>=1 npx playwright test e2e/ui-a11y.spec.ts --project=chromium
```

## Blocking semantics summary

| Gate | Default (CI / no env) | Loop mode |
|---|---|---|
| G1 | blocks on new token drift in diff | same (run each loop) |
| G2 | report-only | `UI_WIRING_STRICT=1` (+ optional `UI_WIRING_DYNAMIC=1`) |
| G3 | normal Playwright assertions | add/maintain screenshot baselines |
| G4 | report-only | `UI_A11Y_STRICT=1` |

## Adding routes to the gate pack

Routes are discovered from the adapter's `routesGlob`. To add a surface:

1. Add a route module matching `routesGlob` with `{ path, name }` entries.
2. Add deterministic mocks for route APIs so pages render without backend dependency.
3. Ensure render guards skip auth-wall/error-boundary states using adapter guard headings.

For focused runs, set `UI_LOOP_ROUTE_FILTER` to a comma-separated list of route
name/path fragments. It matches either descriptor `name` or `path` and fails
loudly if nothing matches, so stale broad routes cannot silently block a target
surface's Detect pass.

## a11y burn-down protocol

Adapter's `a11yAllowlist` maps route -> accepted axe rule IDs:

```json
{
  "/your-route": ["color-contrast"]
}
```

- Fix violations first; only allowlist triaged items with tracking context.
- Remove at least one allowlist entry per iteration until empty.
- Strict mode (`UI_A11Y_STRICT=1`) **honors the allowlist** and fails on any
  *un-triaged* violation (it is not "true zero"); shrink burn-down entries over time.

### Design-system exceptions (distinct from burn-down)

Some surfaces intentionally ship a *modified* design system whose palette is a
deliberate product choice (e.g. VMC's Trading Lab + Bloomberg terminal aesthetic:
dense 8-9px uppercase badges, accent-on-dark micro-labels). Their `color-contrast`
findings are **accepted design-system exceptions**, not burn-down items — they do
not trend to zero. Record them in the allowlist with these guardrails:

- Allowlist **only** the design-driven rule (`color-contrast`) on **only** those
  routes. Never allowlist structural rules (`aria-required-children/parent`,
  `aria-prohibited-attr`, `scrollable-region-focusable`) — broken semantics are
  real bugs regardless of palette.
- Keep at least one **non-exempt** route that shares the global shell (e.g. the
  Today route) with no allowlist entries, so shell regressions still fail strict
  (that route is the "true zero" guard).
- Treat the exception as *pending the surface's design authority* on whether the
  palette should meet AA — documented and tracked, never silently ignored.

## Visual baselines (G3)

- Use `toHaveScreenshot()` in responsive specs; commit baseline snapshots.
- Start conservative (`maxDiffPixelRatio` around `0.01`) to avoid AA/font flake.
- Regenerate with `--update-snapshots` only for reviewed intentional visual changes.
- Keep new visual specs opt-in until their first reviewed baselines are generated
  and committed (for example `UI_STAGE_RAIL_VISUAL=1`).

## Triage taxonomy mapping (UI findings)

| Finding | Bucket |
|---|---|
| Wrong token / non-shared component / style drift | `UI-UX wiring` |
| Control present but inert | `missing-wiring` |
| Handler throws / wrong destination | `bug` |
| Breakpoint overflow / layout collapse | `UI-UX wiring` |
| axe violation (contrast/roles/names) | `UI-UX wiring` (or `bug` if functional) |
| Required UX behavior absent | `gap` (Enhance candidate -> Edge-3) |
| New failure vs baseline | `regression` |

## Enhancement scope-note template

```md
# Enhance scope — <surface> (<yyyy-mm-dd ET>)
owns:
  - <adapter app UI paths>
forbidden:
  - <adapter data-layer / out-of-scope paths>
intended change: <one sentence>
success criteria:
  - <measurable UI/UX outcome>
  - all G1–G4 pass; zero regressions
approval: <operator> @ <time ET>
```

Validate ownership before commit:

```bash
bash .cursor/skills/project-orchestrator/scripts/scope-check.sh
```

## Hard-stop example (kernel format)

```yaml
stop_reason: scope_guard_violation
phase_or_loop: enhance
attempt: 1
failed_checks:
  - command: "bash .cursor/skills/project-orchestrator/scripts/scope-check.sh"
    exit_code: 1
evidence_paths:
  - .orchestrator/<slug>/enhance/scope-check.log
next_action: "Escalate to project-orchestrator for re-spec; enhancement touched a forbidden path."
```
