---
name: plx-portal-agent-access
description: >-
  Authenticate to the PLX customer portal as the dedicated agent staff account and
  run the UI gate against authenticated staff pages. Also runs UAT batch retest
  smokes (per-ticket pageUrl markers after a batch deploy). Use when an agent
  needs to log into staging.plxcustomer.io headlessly, smoke-test staff-gated
  /mrp or /operations pages, validate a UAT session-batch fix on staging, source
  agent-staff or staging/UAT DB credentials, run a11y/wiring/responsive checks or
  Playwright screenshots + axe, or re-provision the agent staff account.
---

# PLX Portal — Autonomous Agent Access & UI Gate

Lets a headless agent (Cursor/Claude/CI) log into the **staff** PLX portal and
verify pages render — with **no browser-typed passwords and no auth-bypass code**.
It uses a real low-privilege STAFF account via the normal NextAuth credentials flow.

## Security invariants (always)

- **Staging + UAT only.** Never touch production (`plx-postgres` with no `-staging`/`-uat`).
- **Never print credentials** to chat/logs or commit them. Scripts read creds from
  the process env / gitignored files only.
- The agent account is **least-privilege STAFF**, rotatable, stored in AWS.

## Credentials (AWS Secrets Manager)

Secret `staging/ec2-secrets` (region `us-east-1`) holds:

| Key | Use |
|---|---|
| `PLX_E2E_EMAIL` / `PLX_E2E_PASSWORD` | agent staff login (account `cos@petrasoap.com`) |
| `DATABASE_URL` | staging Postgres URL (`plx-postgres-staging`) for migrations/queries |

Load into the env without printing (PowerShell):

```powershell
$env:PYTHONUTF8 = '1'
$j = (aws secretsmanager get-secret-value --region us-east-1 --secret-id staging/ec2-secrets `
      --query SecretString --output text) | ConvertFrom-Json
$env:PLX_E2E_EMAIL = $j.PLX_E2E_EMAIL; $env:PLX_E2E_PASSWORD = $j.PLX_E2E_PASSWORD
```

bash + jq: `export PLX_E2E_PASSWORD="$(aws secretsmanager get-secret-value --region us-east-1 --secret-id staging/ec2-secrets --query SecretString --output text | jq -r .PLX_E2E_PASSWORD)"`

## Quick gate (no install) — RUN THIS FIRST

Headless NextAuth login + rendered-DOM checks (status, accessible names, dead
links, responsive grids) on authed sections. From the app dir (e.g. `portal/`):

```bash
node scripts/agent-smoke-login.mjs            # auth only
PROJECT_ID=99 node scripts/agent-smoke-login.mjs   # auth + assert page markers
```

If the repo lacks the script, copy it from this skill: `scripts/agent-smoke-login.mjs`.

## First-class gate (most complete) — Playwright + axe

Real per-viewport screenshots + a true WCAG axe scan, creds from env (no exposure),
session cached via `storageState` (log in once). One-time setup in the app dir:

```bash
npm i -D playwright axe-core
npx playwright install chromium
```

Then run the harness (this skill's `scripts/ui-gate-playwright.mjs`):

```bash
SMOKE_BASE=https://staging.plxcustomer.io PROJECT_ID=99 node scripts/ui-gate-playwright.mjs
```

It logs in once, iterates the configured routes × {desktop, tablet, mobile},
writes screenshots + `axe-summary.json` to `artifacts/ui-gate/`, and exits non-zero
on serious/critical axe violations. Tune routes/viewports at the top of the script.

## If login fails (re-provision the account)

`CredentialsSignin` usually means the account drifted (wrong role, password not
matching the secret) OR you're hitting the wrong DB. Re-align on **staging + UAT**:

```bash
node scripts/provision-agent-staff-account.mjs
```

Requires `STAGING_DATABASE_URL` + `DATABASE_URL` (UAT) in the gitignored
`.env.local` and `PLX_E2E_*` in env. Guarded by `assertAgentWritable` (refuses prod).

## Gotchas (read [reference.md](reference.md) for detail)

- The deployed **`staging.plxcustomer.io` app authenticates against
  `plx-postgres-uat`** today (not `-staging`) — the account must be correct in UAT.
- Staff access is gated by the **legacy `app_user.role` text column** (`'STAFF'`),
  which `isStaff()` checks — the `UserRole` **enum has no `STAFF` label**, so set
  the legacy column, not the enum.
- The new-screen UI lives on **detail pages** (`/mrp/...[id]`), not list pages;
  the auth middleware `307`-redirects all unauthenticated `/api/**` and pages.

## Scripts (read or execute)

- `scripts/agent-smoke-login.mjs` — headless login + rendered-DOM smoke (no deps).
- `scripts/ui-gate-playwright.mjs` — first-class screenshots + axe (needs playwright, axe-core).
- `scripts/provision-agent-staff-account.mjs` — idempotent STAFF re-provision (needs pg, bcryptjs).

---

## UAT batch retest smoke (v1 validator)

Use after a UAT session-batch PR has merged and staging is Ready — **before or
alongside** retest email. Proves the fixed routes load for staff; it does **not**
set Resolution = Verified (submitter-owned).

### Inputs

| Field | Required | Notes |
|---|---|---|
| `{{BATCH_ID}}` | yes | e.g. `B3` |
| `{{TICKET_IDS}}` | yes | SharePoint list item IDs |
| Per ticket `pageUrl` | yes | From UAT Feedback |
| Optional markers | no | Accessible names / text from the diagnosis card |

### Steps

1. Base URL **only** `https://staging.plxcustomer.io` (never vercel.app git alias)
2. Load agent staff creds (section above) — do not print passwords
3. Login via `agent-smoke-login.mjs` or Playwright harness
4. For each ticket: open `pageUrl` (resolve relative paths against staging base)
5. Assert HTTP/render success + any declared markers; record pass/fail per ticket
6. Write evidence to `artifacts/uat-batch-smoke/{{BATCH_ID}}.json` (create dirs as needed):

```json
{
  "batchId": "B3",
  "baseUrl": "https://staging.plxcustomer.io",
  "tickets": [{ "id": "106", "pageUrl": "/mrp/...", "pass": true, "notes": "" }],
  "verdict": "OK"
}
```

7. Report:

```text
BATCH_SMOKE: OK|FAIL|SKIP
- batch:
- tickets_passed / failed:
- evidence: artifacts/uat-batch-smoke/{{BATCH_ID}}.json
- blockers:
```

### Rules

- `SKIP` only with Vince OK or documented STOP (e.g. no stable pageUrl) — log in WEEKLY-LOG
- Failures do **not** auto-Failed-Retest tickets; worker notes them and may still email
  with honest “known gap” language, or ask Vince before emailing
- Never claim Verified

### Done when (batch smoke)

- [ ] `BATCH_SMOKE: OK` **or** `FAIL`/`SKIP` with evidence path + reason
- [ ] Evidence JSON written when not skipped
