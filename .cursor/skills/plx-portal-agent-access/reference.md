# Reference — PLX Portal Agent Access & UI Gate

## Database targeting (why login can fail)

The branch ↔ DB map is `scripts/db-targets.json` in the repo. As of 2026-06, the
deployed **`staging` branch / `staging.plxcustomer.io`** Vercel app reads from
**`plx-postgres-uat`**, while dev work + the FM 30-min sync land on
`plx-postgres-staging`. Implications:

- For the deployed staging app to authenticate the agent account, the account must
  be correct **in UAT**. The provision script writes **both** staging + UAT.
- Gold-table migrations likewise must be dual-applied (staging + UAT). The repo's
  `portal/tmp/apply-migration.mjs` reads `STAGING_DATABASE_URL` (from `.env.local`)
  and `DATABASE_URL` (UAT) and applies to both.
- Production hosts (`plx-postgres` with no suffix) are banned; `assertAgentWritable`
  in `scripts/db-targets.mjs` enforces the allow-list.

## Auth model

- NextAuth v4 credentials provider (`portal/src/lib/auth/auth.ts`). `authorize()`
  looks up `db.user` by email, checks `is_active`, bcrypt-compares `hashed_password`,
  and returns `{ id, email, name, role: user.role, ... }`. The session/JWT `role`
  is the **legacy text `role` column** — that is what `isStaff()` / `requireRole()`
  evaluate.
- `UserRole` enum values: ADMIN, MANAGER, OPERATOR, QC_ANALYST, R_AND_D, PROCUREMENT,
  SALES, ACCOUNTING, CUSTOMER, SUPPLIER — **no STAFF**. Role hierarchy used by the
  guards (`portal/src/lib/auth/roles.ts`): SUPER_ADMIN > ADMIN > MANAGER > STAFF >
  CUSTOMER/SUPPLIER. So a staff agent needs legacy `role='STAFF'` (or higher).
- 2FA: keep the agent account `two_factor_enabled=false` so headless login is one step.

## Headless login flow (no browser)

1. `GET /api/auth/csrf` → `{ csrfToken }`, capture cookies.
2. `POST /api/auth/callback/credentials` (form-encoded: `csrfToken`, `email`,
   `password`, `callbackUrl`, `json=true`), sending the csrf cookie. Success sets a
   `*session-token` cookie and returns `{ url }` without `error=`.
3. Reuse the cookie jar for subsequent `GET`s. A `3xx` to `/login` or `/verify-2fa`
   means not authed / not authorized.

## UI gate dimensions

- **G1 tokens** — components use only `var(--p-*)` design tokens (no raw hex).
- **G2 wiring** — every control has a real handler; no `href="#"` dead links.
- **G3 responsive** — multi-column grids use `repeat(auto-fit, minmax(...))` so they
  reflow on tablet/mobile; verify with screenshots at desktop/tablet/mobile.
- **G4 a11y** — every `<select>`/`<input>`/`<textarea>` has an accessible name
  (`aria-label` or wrapping `<label>`); images have `alt`; axe WCAG 2.x A+AA clean.

The quick gate checks G2/G3/G4 against server-rendered authed HTML (controls behind
toggles/dialogs won't be in first paint — that's expected). The Playwright gate
hydrates the page, so it can open dialogs/tabs and run axe on the live DOM.

## Re-provision details

`provision-agent-staff-account.mjs` sets, for `PLX_E2E_EMAIL` on both DBs:
`role='STAFF'`, `hashed_password=bcrypt(PLX_E2E_PASSWORD)`, `is_active=true`,
`two_factor_enabled=false`, `temp_password_expires_at=NULL`. Idempotent.

## Artifacts

The Playwright gate writes to `artifacts/ui-gate/`:
- `<route-slug>-<viewport>.png` screenshots
- `axe-summary.json` — `{ route, viewport, violations: [{ id, impact, nodes }] }[]`

Keep these out of git unless you want them as evidence bundles (artifacts/ is the
repo's evidence location per repo-hygiene).
