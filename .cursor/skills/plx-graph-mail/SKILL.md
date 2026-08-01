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
- Helper (attachments): `scripts/reports/send-graph-attachments.mjs` in
  `plx-customer-portal` when present; otherwise body-only Graph `sendMail`
- Do **not** use Resend `onboarding@resend.dev` for real customer/staff sends
- Probe send-as-`cos@` once before the first live UAT week if unproven

## Steps

1. `. $HOME/.secrets-env.staging.ps1` (loads Graph / Azure app creds from `~/.aws/*.txt`)
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

## Related

- UAT batch worker: `uat-feedback-batch-fix`
- Weekly loop: `uat-weekly-batch-loop`
- Quote packs may also use `report-export` for attachments
