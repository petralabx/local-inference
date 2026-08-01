---
name: plx-graph-mail
description: >-
  Send email via Microsoft Graph app-only Mail.Send for PLX operator workflows.
  Default From cos@petrasoap.com; use when sending UAT retest mail, quote packs,
  or ops digests. Enforces staging.plxcustomer.io URLs and never uses the
  vercel.app git alias. Use on the Windows workstation after sourcing
  ~/.secrets-env.staging.ps1.
---

# PLX Graph Mail

App-only Graph mail for PLX operator workflows. Prefer this over Resend for
real sends on the Windows workstation (`Mail.Send` verified).

## Preferences

- **From:** `cos@petrasoap.com` unless Vince names another mailbox
- **UAT retest:** To submitters only · BCC `vince@petrasoap.com`
- **Staging links:** only `https://staging.plxcustomer.io`
- **Never** include `*-git-staging-*.vercel.app` (lags; causes false "not shipped")
- Transport: Graph app-only `Mail.Send`
- The credential may only send as `cos@`; every other mailbox returns 403 by design
- Helper (attachments): `scripts/reports/send-graph-attachments.mjs` in
  `plx-customer-portal` when present; otherwise body-only Graph `sendMail`
- Do **not** use Resend `onboarding@resend.dev` for real customer/staff sends
- Probe send-as-`cos@` once before the first live UAT week if unproven

## Steps

1. Workstation: `. $HOME/.secrets-env.staging.ps1` (pulls the credential from AWS
   Secrets Manager `plx/prod/m365/cursor-graph/v1`). Cloud agents already have
   `MICROSOFT_GRAPH_*` injected — skip this step.
2. Build body from the **approved** template (UAT →
   `.orchestrator/uat-weekly-batch-loop/SPEC.md` §7 when present)
3. Validate recipients (submitters only for UAT) and URL ban-list
4. Send via Graph; capture message id / Graph response
5. Log recipients + outcome in WEEKLY-LOG, report path, or session notes
6. On failure: one diagnosis pass, then ask Vince — no retry storms

## Done when

- [ ] Correct From / To / BCC
- [ ] No vercel.app git-alias URL in body
- [ ] Send succeeded **or** blocker reported with Graph error evidence
- [ ] Recipients + outcome logged

## Admin scripts

Tooling for the credential itself — none of these send operator mail. All need an
Exchange or Entra admin session, so hand them to Vince rather than running them.

- `scripts/verify-graph-app.ps1` — token, granted roles, drive read, allowed send,
  and negative send/read probes. Run this first when mail breaks.
- `scripts/scope-mail-to-mailbox.ps1` — binds the `RestrictAccess` policy limiting
  which mailboxes the app may touch. This is the only mechanism that actually
  restricts app-only mail access.
- `scripts/diagnose-mail-scope.ps1` — read-only triage for a 403: mailbox type,
  policy binding, scope-group members, RBAC assignments.
- `scripts/apply-mail-rbac.ps1` — Exchange RBAC for Applications assignments. These
  are additive grants and do **not** replace the policy above.
- `scripts/revoke-excess-graph-roles.ps1` — drop consented app roles beyond the
  brief. Removing a permission under App registrations does not revoke the grant
  on the service principal.

## Related

- UAT batch worker: `uat-feedback-batch-fix`
- Weekly loop: `uat-weekly-batch-loop`
- Quote packs may also use `report-export` for attachments
