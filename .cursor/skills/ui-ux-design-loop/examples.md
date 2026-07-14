# ui-ux-design-loop — Worked Examples

Concrete loop runs. Each assumes a worktree off `origin/main`, a slug under
`.orchestrator/<slug>/`, and an adapter-backed local preview.

## Example 1 — Framework-neutral responsive regression (manifest-driven)

Adapter (`ui-loop.config.json`) excerpt:

```json
{
  "appDir": "apps/acme-web",
  "viewports": ["chromium", "tablet", "mobile-chrome"],
  "baseUrlEnv": "E2E_BASE_URL",
  "authBypassEnv": "LOCAL_AUTH_BYPASS"
}
```

**Detect (G3).**

```bash
bash .cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh \
  --spec e2e/pricing-layout.spec.ts
# FAIL: [tablet] horizontal overflow at 834px
```

**Triage.** Overflow only in the tablet tier (`UI-UX wiring`): fixed-width rail +
long labels in the 768–1024px band.

**Fix.** Convert fixed widths to tokenized responsive layout; add a tablet
assertion and baseline:

```bash
bash .cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh \
  --spec e2e/pricing-layout.spec.ts --projects "tablet" --update-snapshots
```

**Regression.** Re-run full matrix and confirm desktop/mobile are unchanged:

```bash
bash .cursor/skills/ui-ux-design-loop/scripts/ui-responsive-matrix.sh
```

## Example 2 — VMC accessibility burn-down on `/vmc`

**Detect (G4 strict).**

```bash
cd apps/vmc-web
VMC_LOCAL_AUTH_BYPASS=1 UI_A11Y_STRICT=1 npx playwright test e2e/ui-a11y.spec.ts --project=chromium
# FAIL: [a11y][chromium] /vmc: color-contrast (serious) x8
```

**Triage.** `color-contrast` findings on muted chips (`UI-UX wiring`).

**Fix.** Move to accessible token pair and add/extend assertion coverage; rerun G4.

**Burn down.** For design-dependent items, triage in
`apps/vmc-web/e2e/ui-a11y-allowlist.json` with tracking context, then remove
entries each loop until empty.

**Audit + regression.** Auditor confirms fail->pass deltas and no cross-viewport
regressions in the matrix.

## Example 3 — Dead control wiring (generic G2 strict)

**Detect (G2 strict + dynamic).**

```bash
cd <adapter.appDir>
<adapter.authBypassEnv>=1 UI_WIRING_STRICT=1 UI_WIRING_DYNAMIC=1 \
  npx playwright test e2e/ui-wiring-sweep.spec.ts --project=chromium
# one enabled button has no observable effect
```

**Triage.** Control is intended to trigger refresh, so bucket `missing-wiring`
(not inert/decorative).

**Fix.** Wire handler to existing action; add focused test (red->green). If a
control is truly inert, mark it `data-ui-inert`.

**Verify.** Re-run G2 strict; expect zero dynamic/static dead controls.

## Example 4 — Gated enhancement after defects are clear

Detect is green across G1–G4. Operator requests a readability polish pass.

1. Write `.orchestrator/<slug>/enhance/SCOPE.md` from the reference template
   (owns + forbidden are adapter-specific).
2. Operator approves the scope for this run only.
3. `critic` proposes spacing/hierarchy tweaks within scope; fixer implements;
   G1–G4 must still pass with zero regressions.
4. A request to modify out-of-scope backend/data files triggers Edge-3
   escalation to `project-orchestrator` (re-spec), not a silent edit.
