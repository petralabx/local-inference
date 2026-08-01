---
name: staging-dual-db-migrate
description: >-
  Apply PLX gold-table / Prisma migrations safely to BOTH plx-postgres-staging
  and plx-postgres-uat. Use when adding schema, fixing "relation does not exist"
  on staging.plxcustomer.io, UAT remediation migrations, or any change that must
  land on both agent-writable DBs. Never production.
---

# Staging Dual-DB Migrate

`staging.plxcustomer.io` currently reads **`plx-postgres-uat`**. Dev work + the
FM 30-min sync land on **`plx-postgres-staging`**. Gold-table migrations that
only hit one host leave the deployed app broken even when "migration succeeded."

## Preferences

- Always apply to **both** staging and uat until the dedicated UAT branch split
- Preflight: load staging secrets, then `bash scripts/assert-staging-context.sh`
- Prefer `listMigrationTargetUrls()` / `assertAgentWritable` from
  `scripts/db-targets.mjs` (single source of truth: `scripts/db-targets.json`)
- Never touch production host `plx-postgres` (no `-staging` / `-uat` suffix)
- Never source production secrets (`~/.secrets-env`)
- Strip `sslmode` quirks via `stripSslmodeFromUrl` when RDS verify-full fails

## Steps

1. Confirm the change is gold/Prisma (not FM replica lowercase tables)
2. Windows: `. $HOME/.secrets-env.staging.ps1` · Linux: `source ~/.secrets-env.staging`
3. Run `bash scripts/assert-staging-context.sh` — read the success line host
4. Dry-check state on both hosts (e.g. `scripts/sql/check-uat-remediation-state.mjs`
   or an equivalent probe)
5. Apply to **staging**, then **uat** (or iterate `listMigrationTargetUrls()`)
6. Re-verify both; smoke the affected route on `https://staging.plxcustomer.io`
7. If GRANT / `plxadmin` ownership blocks ALTER — follow
   `docs/runbooks/UAT-REMEDIATION-MIGRATION-DEPLOY.md`; do not invent workarounds

## Done when

- [ ] Migration applied on **staging and uat**
- [ ] Verification query/script green on **both**
- [ ] Staging URL smoke OK (or failure explained with host evidence)
- [ ] No production host touched
- [ ] Evidence recorded (commands + hosts) for the PR / WEEKLY-LOG / MC complete

## Related

- Portal staging policy: `.cursor/rules/staging-environment.mdc`
- Targeting doc: `docs/runbooks/DATABASE-TARGETING.md`
