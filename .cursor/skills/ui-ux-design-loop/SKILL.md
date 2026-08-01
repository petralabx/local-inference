---
name: ui-ux-design-loop
description: Drive any web surface to near-perfect UI/UX quality with a bounded convergence loop specialized for design-system conformance, interaction wiring, responsive integrity, and accessibility. Composes project-hardener (does not fork the loop engine) and adds a manifest-driven UI gate pack — G1 tokens/components, G2 dead-control sweep, G3 responsive matrix, G4 axe accessibility — plus a scope-gated enhancement phase. Use when the user asks for "UI/UX loop", "harden the UI", "design-system alignment", "fix dead buttons/wiring", "responsive polish", or "accessibility pass" on a web route.
---

# UI/UX Design Loop

A domain-specialized convergence loop for web UI surfaces. It maps the operator's
loop — **test -> find -> fix -> harden -> (gated) enhance -> repeat** — onto the
existing bounded engine instead of building a second one.

This skill **composes**, it does not replace:

- [project-hardener](../project-hardener/SKILL.md) owns the bounded
  detect -> triage -> fix -> audit -> regression-gate loop, the triage taxonomy
  (which already names `UI-UX wiring` and `missing-wiring`), stop conditions,
  and Edge-3 escalation.
- [orchestration-kernel](../orchestration-kernel/SKILL.md) owns role-based model
  resolution, scope-lock, evidence-bundle shape, drift detectors, and the
  hard-stop YAML.

This skill adds only the genuinely-missing UI pieces: a **UI gate pack**
(G1–G4) wired into the hardener's Detect step, and a scope-gated **Enhance** phase.

## Adapter Contract (manifest-driven)

Repo-specific bindings come from `ui-loop.config.json` (or `UI_LOOP_CONFIG`) resolved
by `scripts/ui-loop-config.mjs`.

- The manifest provides repo/app-specific values such as `appDir`, `viewports`,
  `baseUrlEnv`, route discovery, render guards, token-check command, and a11y allowlist.
- The skill stays framework-agnostic; adapter specifics live in [reference.md](reference.md).
- The VMC adapter is the reference implementation for this repository.

## When to Use

- A web route/surface needs UI hardening: design-system drift, dead or unlabeled
  controls, broken responsive layout, or accessibility gaps.
- The user asks for "UI/UX loop", "design-system alignment", "fix the wiring",
  "responsive polish", "a11y pass", or "make this screen near-perfect".
- You want a bounded, evidence-backed loop — not an open-ended redesign.

## When NOT to Use

- Pre-build discovery or spec work (use `project-researcher` /
  `project-orchestrator`).
- A single known defect (use `root-cause-debugger`).
- Non-UI backend convergence (use `project-hardener` directly).
- Open-ended "redesign the product" requests — the Enhance phase is scope-gated,
  not a blank check.

## Prerequisites (environment)

Browser validation runs against a **local preview** (never a shared/production server).
Use the adapter's `appDir`, `previewCommand`, and auth bypass env:

```bash
cd <adapter.appDir>
npm ci      # once per worktree
<adapter.authBypassEnv>=1 <adapter.previewCommand> -- --hostname 127.0.0.1 --port <free-port>
```

Live UI evidence (snapshots/screenshots/CDP) uses the `cursor-ide-browser` MCP;
follow [autonomous-verifier](../autonomous-verifier/SKILL.md) snapshot-first
rules. Optional design targets to diff against come from the `user-aidesigner`
MCP (keep preview/adoption local). This loop assumes **no outbound network** is
required at runtime (axe runs in-page; screenshots are local).

## The UI Gate Pack (added to Detect)

Each gate is non-blocking by default (report + annotate) and becomes a hard
Detect gate under its `*_STRICT` switch — that is the mode the loop runs.

| Gate | Concern | Run it | Blocking switch |
|---|---|---|---|
| **G1** | Design-system conformance (tokens + shared components) | `.cursor/skills/ui-ux-design-loop/scripts/ui-conformance-scan.sh --base origin/main` | blocks on new raw-color findings in changed files |
| **G2** | Interaction wiring (dead/unlabeled controls) | `cd <adapter.appDir> && npx playwright test e2e/ui-wiring-sweep.spec.ts` | `UI_WIRING_STRICT=1` (+ opt-in `UI_WIRING_DYNAMIC=1`) |
| **G3** | Responsive integrity (desktop/tablet/mobile + screenshots) | `.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh` | Playwright assertions / `toHaveScreenshot` diffs |
| **G4** | Accessibility (axe WCAG 2.x A+AA) | `cd <adapter.appDir> && npx playwright test e2e/ui-a11y.spec.ts` | `UI_A11Y_STRICT=1` |

- **G1** reads command/args/file globs from the adapter manifest and judges only
  the loop's own diff (zero new drift policy).
- **G3** reads the responsive project matrix from `viewports` and supports optional
  Safari via `--include-safari`; visual baselines use Playwright `toHaveScreenshot()`.
- **G4** uses `@axe-core/playwright`; allowlist file is adapter-bound and should be
  burned down toward zero.

Annotate intentionally-inert controls (decorative/disabled) with
`data-ui-inert` so G2 does not flag them. Gate thresholds, route extension, and
the burn-down protocol are in [reference.md](reference.md).

## Loop Lifecycle

Run the hardener loop with the UI gate pack folded into Detect:

```text
0) Baseline      — hardener baseline snapshot + capture current G1–G4 state
1) Detect        — full suite + lint + typecheck + E2E, AND G1–G4 (strict)
2) Triage        — hardener taxonomy: bug | UI-UX wiring | missing-wiring | gap | regression
3) Fix           — fixer: failing test first, smallest scoped diff (tokens/wiring/responsive/a11y)
4) Audit         — independent read-only auditor verifies fail->pass + no scope creep
5) Regression    — regression-diff vs baseline; zero new failures across all viewports
6) Enhance       — ONLY when defects are clear AND scope is approved (see below)
   repeat 1–6 until fixpoint or a hard stop
```

Use the hardener scripts for steps 0 and 5:

```bash
bash .cursor/skills/project-hardener/scripts/baseline-snapshot.sh \
  --out .orchestrator/<slug>/hardener/baseline.env \
  --tests-cmd "cd <adapter.appDir> && npm run test" \
  --e2e-cmd  "cd <adapter.appDir> && <adapter.authBypassEnv>=1 bash ../../.cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh" \
  --lint-cmd "cd <adapter.appDir> && npm run lint" \
  --typecheck-cmd "cd <adapter.appDir> && npm run typecheck"
```

## Roles (role-based, resolved at runtime)

Name roles, never model slugs (per orchestration-kernel). Resolve best-available
per criteria; freeze the mapping for the run.

| Role | Selection criteria | Responsibility in this loop |
|---|---|---|
| planner | strongest reasoning model, high thinking budget | frame the surface, triage, sequence gates, decide fixpoint |
| builder/fixer | strongest coding model, balanced speed | scoped UI fixes (tokens, wiring, responsive, a11y) + failing-first test |
| auditor | capable model from a **different family** than fixer | independent read-only verification; reject scope creep |
| mechanical | fastest low-cost model | snapshot/evidence capture, gate aggregation, allowlist edits |
| critic | capable adversarial model | design/a11y review during the Enhance phase only |

Map to the repo's `.claude/agents` fixer/validator/auditor and Task subagents.

## Enhance Phase (scope-gated)

The hardener blocks silent enhancement. Enhancement here is a **separate,
approved, per-run phase**, never folded into the fix loop:

1. Enter Enhance **only after** Detect is green (no open high-severity UI
   findings) and regression is clean.
2. Write an enhancement scope note: exact surfaces, intended change, success
   criteria, and an explicit `owns`/`forbidden` glob set.
3. Get operator approval for that scope (per-run, not a standing budget).
4. Run fixer + `critic` within the locked scope; any change beyond it triggers
   **Edge-3 escalation** to `project-orchestrator` (re-spec) or
   `project-researcher` (re-research) — see the kernel's hard-stop format.

The enhancement scope-note template is in [reference.md](reference.md).

## Done-Definition and Stop Conditions

Inherit the hardener fixpoint, extended with the gate pack:

- Standard suite + lint + typecheck + E2E clean.
- G1 zero new token drift; G2 zero un-annotated dead controls (strict); G3 all
  viewport assertions/screenshots pass; G4 zero un-triaged axe violations on
  in-scope routes (allowlist burned down per plan).
- Regression diff shows zero new failures vs baseline across all viewports.
- The most recent full loop produced no new fixes (fixpoint).

Honor the hardener hard stops (`max_loops_reached`, `no_progress_or_oscillation`,
`unfixable_regression`, `evidence_missing`, `scope_guard_violation`) and emit the
kernel hard-stop YAML with evidence paths on halt.

## Evidence

Use the kernel evidence bundle at `.orchestrator/<slug>/` (baseline, per-loop
gate logs, screenshots, regression diff, REPORT.md). Never claim a gate passed
without the command output. For VMC roadmap/todo-linked work follow
[vmc-sync](../vmc-sync/SKILL.md) and gate commits with
[wterm-preflight](../wterm-preflight/SKILL.md).

## Additional Resources

- Gate cookbook, thresholds, route extension, burn-down + enhance templates:
  [reference.md](reference.md)
- Worked loop runs: [examples.md](examples.md)
- Scripts: [scripts/ui-conformance-scan.sh](scripts/ui-conformance-scan.sh),
  [scripts/ui-responsive-matrix.sh](scripts/ui-responsive-matrix.sh)
- Composed spines: [project-hardener](../project-hardener/SKILL.md),
  [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Composed tools: [autonomous-verifier](../autonomous-verifier/SKILL.md),
  [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md),
  [parallel-multiagent-orchestrator](../parallel-multiagent-orchestrator/SKILL.md)
