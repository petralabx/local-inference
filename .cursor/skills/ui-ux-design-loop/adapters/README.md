# UI Loop Adapter Authoring Guide

This folder holds repo-specific adapter manifests for the `ui-ux-design-loop` skill.
The manifest contract is defined by `ui-loop.schema.json` at repo root and loaded by:

- `node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --key <dot.path>`
- `node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --validate <path>`

Use this guide when onboarding a new repository.

## 1) Copy-paste starter manifest

Create a new `ui-loop.config.json` with all required keys:

```json
{
  "appDir": "web",
  "tokenCheck": {
    "command": "node",
    "args": ["scripts/check-theme-tokens.mjs"],
    "fileGlobs": ["web/src/**/*.tsx"]
  },
  "componentMap": ["PrimaryButton", "PageHeader"],
  "routesGlob": "web/e2e/helpers/ui-loop/*.routes.ts",
  "renderGuard": {
    "authHeading": "Sign in",
    "errorHeading": "Something went wrong"
  },
  "a11yAllowlist": "web/e2e/ui-a11y-allowlist.json",
  "viewports": ["chromium", "tablet", "mobile-chrome"],
  "baseUrlEnv": "E2E_BASE_URL",
  "authBypassEnv": "LOCAL_AUTH_BYPASS",
  "previewCommand": "npm run dev"
}
```

Validate immediately:

```bash
node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --validate path/to/ui-loop.config.json
```

## 2) Required key checklist

- `appDir`: app working directory used by UI checks (`cd` target for Playwright/lint commands).
- `tokenCheck.command`: executable for G1 token-conformance checks.
- `tokenCheck.args`: static arguments for the token checker command (`minItems: 1`).
- `tokenCheck.fileGlobs`: globs scanned for style/token drift (`minItems: 1`).
- `componentMap`: shared component names expected by conformance checks.
- `routesGlob`: glob for route modules consumed by UI wiring + a11y sweeps.
- `renderGuard.authHeading`: heading text that means "auth wall rendered, skip page assertions."
- `renderGuard.errorHeading`: heading text that means "error boundary rendered, skip page assertions."
- `a11yAllowlist`: JSON file path with route-keyed known axe exceptions.
- `viewports`: Playwright project names for desktop/tablet/mobile matrix (`minItems: 1`).
- `baseUrlEnv`: env var name that points tests to a preview URL.
- `authBypassEnv`: env var name used to bypass auth in local preview.
- `previewCommand`: command used to boot preview for test runs.

## 3) Discover render-guard headings (copy-paste workflow)

1. Boot preview in your app directory (`cd <appDir> && <previewCommand>`).
2. Open one protected route and one route that can intentionally raise an app error.
3. Capture headings from rendered HTML (or browser snapshot) and copy exact text.
4. Set those exact strings in `renderGuard.authHeading` and `renderGuard.errorHeading`.
5. Re-run `--validate` and then run a strict wiring/a11y pass to confirm guards skip only intended pages.

If your app uses dynamic heading text, choose the stable top-level heading rendered across environments.

## 4) Route-module + mock pattern

Keep route modules deterministic and pair them with route-local mocks so sweeps do not depend on live backends.

Example route module:

```ts
export const UI_LOOP_ROUTES = [
  { path: "/orders", name: "Orders" },
  { path: "/inventory", name: "Inventory" }
];
```

Example mock pattern:

```ts
import { Page } from "@playwright/test";

export async function registerUiLoopMocks(page: Page): Promise<void> {
  await page.route("**/api/orders", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify({ data: [] }) });
  });
}
```

Run mocks before route traversal in your UI-loop Playwright specs.

## 5) Viewport and tablet selection

- Reuse existing Playwright project names when available.
- Keep at least one desktop + one mobile project.
- If your repo does not define `tablet`, create one in Playwright config with a stable preset (for example, iPad landscape) and then include `"tablet"` in `viewports`.

Recommended default set when available:

- `chromium`
- `tablet`
- `mobile-chrome`

## 6) Config placement and selection

- Default config path: `<repo-root>/ui-loop.config.json`
- Alternate configs (like this folder): set `UI_LOOP_CONFIG` to a specific file.

Examples:

```bash
UI_LOOP_CONFIG=".cursor/skills/ui-ux-design-loop/adapters/colleague-1/ui-loop.config.json" \
node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --key appDir
```

```bash
node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --validate \
  .cursor/skills/ui-ux-design-loop/adapters/colleague-2/ui-loop.config.json
```

## 7) Adapter folder layout convention

Use one folder per repository:

- `adapters/<repo-slug>/ui-loop.config.json`
- `adapters/<repo-slug>/README.md` (notes, caveats, setup commands)

For unavailable repos, use an explicit placeholder README marked `STUB`.
