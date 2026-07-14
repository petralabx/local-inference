---
name: uat-feedback-batch-fix
description: >-
  Diagnose and fix one PLX UAT Feedback session batch: one PR into staging with
  a plain UAT-Feedback: <ids> stamp, wait for Vercel Ready + mark-ready, then
  email submitters from cos@petrasoap.com to retest. Use when given a session
  batch, a master-prompt pack of UAT tickets, BATCH-WORKER placeholders, or
  when the weekly UAT loop dispatches a single batch. Does not set
  Resolution=Verified.
---

# UAT Feedback Batch Fix

Fix **one** SharePoint UAT Feedback session batch end-to-end. Policy details live
in the portal worktree at `.orchestrator/uat-weekly-batch-loop/SPEC.md` when
present — do not invent conflicting rules.

## Inputs (required)

| Placeholder | Example |
|---|---|
| `{{WEEK_ID}}` | `2026-W28` |
| `{{BATCH_ID}}` | `B3` |
| `{{BATCH_LABEL}}` | `/mrp/batching · manufacturing (5)` |
| `{{TICKET_IDS}}` | `106, 105, 104, 100, 86` |
| `{{SUBMITTER_EMAILS}}` | (if known) |

## Preferences

- Staging only — never `master` / production DB
- Diagnose before code (portal `prompt-export.ts` / master-prompt pack)
- **One PR per batch** into `staging`
- PR stamp as **plain lines** (not fences/backticks):

```text
UAT-Feedback: 106, 105, 104, 100, 86
```

- Email only after merge + Vercel Ready on **`https://staging.plxcustomer.io`**
- From: `cos@petrasoap.com` · To: submitters · BCC: `vince@petrasoap.com`
- Never put `*-git-staging-*.vercel.app` URLs in email or tester notes
- Prisma / portal gold tables only — no FM replica UI queries
- Worked example: MRP-M-025 / `7dffe9561` / tickets 106, 105, 104, 100, 86

## Steps

1. Secrets: `. $HOME/.secrets-env.staging.ps1` (Windows) or `source ~/.secrets-env.staging`
2. Load ticket facts; tag gaps `[NEEDS INFO]`; write ranked hypotheses + files to inspect
3. Implement the **smallest** correct fix; typecheck/lint touched areas
4. Open one PR to `staging` with the plain `UAT-Feedback:` stamp; optional dry-run:
   `node scripts/uat-feedback/mark-ready-from-pr.mjs --pr N --dry-run`
5. After merge + Ready: send retest email (prefer **one email per unique submitter**).
   Use skill **plx-graph-mail** / SPEC §7 template when available
6. Append a batch row to `.orchestrator/uat-weekly-batch-loop/WEEKLY-LOG.md` if that file exists

## Done when

- [ ] Diagnosis recorded in the session (and ideally PR body)
- [ ] One staging PR opened/merged **or** blocked with STOP reason
- [ ] Retest email sent after Ready **or** blocked with reason
- [ ] Tickets left in Ready/UATn awaiting submitter **Verified** / **Failed Retest**
- [ ] WEEKLY-LOG batch section written (when orchestrator folder exists)
- [ ] Agent did **not** set Resolution = Verified

## STOP — ask Vince before coding

Critical severity · auth/RBAC/middleware/2FA · schema/migrations · same ticket
Failed Retest ≥ 2 · missing/ambiguous submitter email · scope beyond this batch.

## Related

- Weekly orchestrator: `uat-weekly-batch-loop`
- Graph send: `plx-graph-mail`
- SOP UAT scenarios (different): `uat-runner`
