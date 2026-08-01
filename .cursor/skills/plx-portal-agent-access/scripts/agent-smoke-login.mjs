/**
 * Agent staff login + smoke check (headless, no browser, no auth-bypass).
 *
 * Logs into the PLX portal via the NextAuth credentials flow using the agent
 * staff account from AWS Secrets Manager `staging/ec2-secrets`
 * (`PLX_E2E_EMAIL`/`PLX_E2E_PASSWORD`), then fetches a page and (optionally)
 * asserts PD v8 section markers. Reads creds from env; prints status only.
 *
 * Env: PLX_E2E_EMAIL, PLX_E2E_PASSWORD (required);
 *      SMOKE_BASE (default https://staging.plxcustomer.io);
 *      SMOKE_PATH (default /mrp/project-development);
 *      PROJECT_ID (optional — assert v8 markers on /mrp/project-development/<id>).
 */

const base = (process.env.SMOKE_BASE || "https://staging.plxcustomer.io").replace(/\/$/, "");
const email = process.env.PLX_E2E_EMAIL;
const password = process.env.PLX_E2E_PASSWORD;
const smokePath = process.env.SMOKE_PATH || "/mrp/project-development";
if (!email || !password) {
  console.error("MISSING creds: set PLX_E2E_EMAIL and PLX_E2E_PASSWORD (from AWS staging/ec2-secrets)");
  process.exit(2);
}

const jar = new Map();
const store = (res) => {
  const l = typeof res.headers.getSetCookie === "function" ? res.headers.getSetCookie() : [];
  for (const c of l) { const [p] = c.split(";"); const i = p.indexOf("="); if (i > 0) jar.set(p.slice(0, i).trim(), p.slice(i + 1).trim()); }
};
const cookie = () => [...jar.entries()].map(([k, v]) => `${k}=${v}`).join("; ");

async function login() {
  const csrf = await fetch(`${base}/api/auth/csrf`, { headers: { cookie: cookie() } });
  store(csrf);
  const { csrfToken } = await csrf.json();
  if (!csrfToken) throw new Error("no csrfToken");
  const res = await fetch(`${base}/api/auth/callback/credentials`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", cookie: cookie() },
    body: new URLSearchParams({ csrfToken, email, password, callbackUrl: `${base}${smokePath}`, json: "true" }).toString(),
    redirect: "manual",
  });
  store(res);
  let url = "";
  try { url = (await res.json())?.url || ""; } catch { url = res.headers.get("location") || ""; }
  const hasSession = [...jar.keys()].some((k) => k.includes("session-token"));
  console.log(`login: status=${res.status} session=${hasSession} url=${url.replace(base, "")}`);
  if (/error=/.test(url) || !hasSession) throw new Error("login failed (bad creds / inactive / 2FA)");
}

async function fetchPage(path) {
  const res = await fetch(`${base}${path}`, { headers: { cookie: cookie() }, redirect: "manual" });
  if (res.status >= 300 && res.status < 400) {
    throw new Error(`${path} redirected -> ${(res.headers.get("location") || "").replace(base, "")} (not authed/authorized)`);
  }
  return { status: res.status, html: await res.text() };
}

async function main() {
  await login();
  const page = await fetchPage(smokePath);
  console.log(`page ${smokePath}: status=${page.status}`);
  const projectId = process.env.PROJECT_ID;
  if (!projectId) { console.log("RESULT: PASS — authenticated."); return; }
  const d = await fetchPage(`/mrp/project-development/${projectId}`);
  const m = {
    lifestrip: d.html.includes("lifestrip"),
    sectionNav: /section=(overview|gate|develop|artwork|testing|comms)/.test(d.html),
    goNoGo: d.html.includes("Go / No-Go"),
    subassemblies: d.html.includes("Sub-assemblies"),
    oldPhaseRail: d.html.includes("phaserail"),
  };
  console.log(`detail(${projectId}): status=${d.status} markers=${JSON.stringify(m)}`);
  if (m.lifestrip && m.sectionNav) console.log("RESULT: PASS — v8 section workspace live.");
  else { console.log(m.oldPhaseRail ? "RESULT: FAIL — old phase rail still served." : "RESULT: INCONCLUSIVE."); process.exit(1); }
}
main().catch((e) => { console.error("ERROR:", e.message); process.exit(1); });
