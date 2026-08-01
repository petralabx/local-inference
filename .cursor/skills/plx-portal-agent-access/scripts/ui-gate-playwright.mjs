/**
 * First-class UI gate — Playwright + axe-core, storageState auth.
 *
 * Logs in ONCE as the agent staff account (creds from env, never printed), caches
 * the session via storageState, then for each route × viewport captures a
 * screenshot and runs an axe WCAG 2 A+AA scan on the hydrated DOM. Writes
 * artifacts/ui-gate/<route>-<viewport>.png + axe-summary.json. Exits non-zero on
 * serious/critical violations.
 *
 * Contrast baseline: known brand color-contrast exceptions (foreground hexes)
 * listed in a baseline file are reported but DO NOT fail the gate, so only NEW
 * contrast regressions break the build. Default baseline path:
 * ./ui-gate-contrast-baseline.json (override with UI_GATE_CONTRAST_BASELINE).
 *
 * Setup (in the app dir, once):
 *   npm i -D playwright axe-core && npx playwright install chromium
 * Run:
 *   SMOKE_BASE=https://staging.plxcustomer.io PROJECT_ID=99 node scripts/ui-gate-playwright.mjs
 *
 * Env: PLX_E2E_EMAIL, PLX_E2E_PASSWORD (required); SMOKE_BASE; PROJECT_ID;
 *      ROUTES (optional comma list); UI_GATE_CONTRAST_BASELINE (optional path).
 */
import { chromium } from "playwright";
import axe from "axe-core";
import fs from "node:fs";
import path from "node:path";

const base = (process.env.SMOKE_BASE || "https://staging.plxcustomer.io").replace(/\/$/, "");
const email = process.env.PLX_E2E_EMAIL;
const password = process.env.PLX_E2E_PASSWORD;
const pid = process.env.PROJECT_ID;
if (!email || !password) { console.error("MISSING PLX_E2E_EMAIL/PLX_E2E_PASSWORD"); process.exit(2); }

const defaultRoutes = pid
  ? ["overview", "intake", "gate", "develop", "artwork", "testing", "comms"].map(
      (s) => `/mrp/project-development/${pid}?section=${s}`,
    )
  : ["/mrp/project-development"];
const routes = (process.env.ROUTES ? process.env.ROUTES.split(",") : defaultRoutes).map((r) => r.trim());

const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 834, height: 1112 },
  { name: "mobile", width: 390, height: 844 },
];

// ── Contrast baseline (accepted brand foregrounds) ─────────────────────────────
const baselinePath = process.env.UI_GATE_CONTRAST_BASELINE || "ui-gate-contrast-baseline.json";
let acceptedFg = new Set();
try {
  const b = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
  acceptedFg = new Set((b.acceptedForegrounds || []).map((h) => h.toLowerCase()));
  console.log(`contrast baseline: ${acceptedFg.size} accepted foreground(s) from ${baselinePath}`);
} catch {
  console.log(`contrast baseline: none (${baselinePath} not found) — all contrast fails count`);
}
const rgbToHex = (c) => {
  const m = (c || "").match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  return m ? "#" + [1, 2, 3].map((i) => Number(m[i]).toString(16).padStart(2, "0")).join("").toLowerCase() : (c || "").toLowerCase();
};

const outDir = path.resolve("artifacts/ui-gate");
fs.mkdirSync(outDir, { recursive: true });
const slug = (r) => r.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").slice(0, 60);

const browser = await chromium.launch();
const summary = [];
let failNodes = 0;
let baselinedNodes = 0;

try {
  const ctx0 = await browser.newContext();
  const page0 = await ctx0.newPage();
  await page0.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
  await page0.fill('input[type="email"], input[name="email"], input[placeholder*="@"]', email);
  await page0.fill('input[type="password"]', password);
  await page0.getByRole("button", { name: /sign in/i }).click();
  await page0.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 30000 }).catch(() => {});
  await page0.waitForTimeout(1500);
  const state = await ctx0.storageState();
  await ctx0.close();
  if (!JSON.stringify(state).includes("session-token")) throw new Error("login failed (creds/2FA/role)");
  console.log(`authed as ${email}`);

  for (const vp of viewports) {
    const ctx = await browser.newContext({ storageState: state, viewport: { width: vp.width, height: vp.height } });
    const page = await ctx.newPage();
    for (const route of routes) {
      await page.goto(`${base}${route}`, { waitUntil: "domcontentloaded" }).catch(() => {});
      await page.waitForTimeout(1500);
      const shot = path.join(outDir, `${slug(route)}-${vp.name}.png`);
      await page.screenshot({ path: shot, fullPage: true });
      await page.addScriptTag({ content: axe.source });
      const result = await page.evaluate(async () =>
        await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }),
      );
      const violations = [];
      let routeFail = 0;
      let routeBaselined = 0;
      for (const v of result.violations) {
        const isContrast = v.id === "color-contrast";
        let newNodes = 0, baselined = 0;
        for (const n of v.nodes) {
          const fg = isContrast ? rgbToHex(n.any?.[0]?.data?.fgColor) : null;
          if (isContrast && acceptedFg.has(fg)) baselined++;
          else newNodes++;
        }
        const counts = v.impact === "serious" || v.impact === "critical" ? newNodes : 0;
        routeFail += counts;
        routeBaselined += baselined;
        violations.push({ id: v.id, impact: v.impact, nodes: v.nodes.length, failing: counts, baselined });
      }
      failNodes += routeFail;
      baselinedNodes += routeBaselined;
      summary.push({ route, viewport: vp.name, screenshot: path.relative(process.cwd(), shot), violations });
      console.log(`${vp.name} ${route}: ${routeFail} failing node(s), ${routeBaselined} baselined`);
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(outDir, "axe-summary.json"), JSON.stringify(summary, null, 2));
console.log(`\nWrote ${summary.length} screenshots + axe-summary.json to ${path.relative(process.cwd(), outDir)}`);
console.log(`baselined (known brand contrast): ${baselinedNodes} node(s)`);
console.log(failNodes === 0
  ? "RESULT: PASS — no NEW serious/critical violations (brand-contrast baseline applied)."
  : `RESULT: ${failNodes} new serious/critical node(s) — review axe-summary.json.`);
process.exit(failNodes === 0 ? 0 : 1);
