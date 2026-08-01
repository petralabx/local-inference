/**
 * Provision / re-align the agent staff account on staging + UAT.
 *
 * Sets, for PLX_E2E_EMAIL on both DBs: role='STAFF' (legacy text col that
 * isStaff() checks — the UserRole enum has no STAFF label), password =
 * bcrypt(PLX_E2E_PASSWORD), active, 2FA off, temp expiry cleared. Idempotent.
 *
 * Needs: `npm i pg bcryptjs` available in the app dir. STAGING_DATABASE_URL +
 * DATABASE_URL (UAT) in gitignored .env.local; PLX_E2E_* in env.
 * STAGING/UAT ONLY — refuses production hosts.
 */
import { Client } from "pg";
import bcrypt from "bcryptjs";
import fs from "node:fs";

function readEnvLocal(key) {
  for (const p of [".env.local", "portal/.env.local"]) {
    try {
      const env = fs.readFileSync(p, "utf8");
      const m = env.match(new RegExp(`^${key}="?([^"\\r\\n]+)"?`, "m"));
      if (m?.[1]) return m[1];
    } catch { /* next */ }
  }
  return undefined;
}

// Inline allow-list (mirror of scripts/db-targets.mjs#assertAgentWritable).
function assertAgentWritable(url) {
  if (url.includes("plx-postgres.c2b8m8") && !url.includes("-staging") && !url.includes("-uat")) {
    throw new Error("Refusing — production host");
  }
  if (!/plx-postgres-(staging|uat)|db-staging-backup/.test(url)) {
    throw new Error("Refusing — not an agent-writable host");
  }
}
const strip = (u) => u.replace(/\?.*$/, "");

const email = (process.env.PLX_E2E_EMAIL || "").toLowerCase();
const password = process.env.PLX_E2E_PASSWORD;
if (!email || !password) { console.error("missing PLX_E2E_EMAIL/PLX_E2E_PASSWORD"); process.exit(2); }
const hash = await bcrypt.hash(password, 10);

const targets = [
  { name: "uat", url: process.env.DATABASE_URL || readEnvLocal("DATABASE_URL") },
  { name: "staging", url: process.env.STAGING_DATABASE_URL || readEnvLocal("STAGING_DATABASE_URL") },
];

for (const { name, url } of targets) {
  if (!url) { console.log(`${name}: no url (skipped)`); continue; }
  assertAgentWritable(url);
  const c = new Client({ connectionString: strip(url), ssl: { rejectUnauthorized: false } });
  try {
    await c.connect();
    const r = await c.query(
      `UPDATE app_user SET hashed_password=$2, role='STAFF', is_active=true,
              two_factor_enabled=false, temp_password_expires_at=NULL, updated_at=now()
        WHERE lower(email)=$1`,
      [email, hash],
    );
    console.log(`[${name}] updated rows=${r.rowCount} (role=STAFF, password synced)`);
  } catch (e) {
    console.log(`[${name}] ERROR ${e.message}`);
  } finally {
    try { await c.end(); } catch { /* ignore */ }
  }
}
