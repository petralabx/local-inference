# Buzz pilot playbook (portal + Mission Control)

## Orbit

- **Code / product work:** `plx-customer-portal`
- **PM / task SoR:** Mission Control (`mc.plxcustomer.io`) — Buzz does **not**
  replace MC checkout, stamps, or compliance
- **Room:** Buzz channels on self-hosted `BUZZ` at
  `wss://buzz.tail7cdeae.ts.net` (`petrasoap.com` tailnet)
- **Bootstrap room:** `Welcome`
  (`ee508854-2cc1-4bc5-87ca-7dfe7699d8a8`); Hermes and Cursor are bot members
  and passed the corporate-relay mention smoke on 2026-08-10

## Channel pattern

1. Pick (or create) an MC task for the portal work.
2. Create a Buzz channel named after the task / short slug
   (e.g. `portal-TASK-NNN-short-title`).
3. Invite Vince, Ricardo, Stephen + Hermes + Cursor agents.
4. Pin: MC task URL, PR links, non-goals, L5 allowlist reminder.

## Ritual — feedback before long runs

Before a long agent/dev run:

1. Author posts intent + constraints in the channel.
2. Humans and/or agents respond (risk, scope, “don’t do X”).
3. Only then start the long run (Cursor/Hermes/Cloud as usual).
4. Drop PR / evidence links back into the same channel.

## Success verdict (from discovery L6)

Pilot succeeds when **both** hold:

1. Room works (three humans daily-ish; Hermes + Cursor @mentionable; at least one
   real portal thread got feedback before a long run).
2. A real portal project is completed using Buzz as the collaboration room.

**Signers:** Vince **and** Ricardo (joint). Stephen participates; not a required
signer.

Fill `EVIDENCE-PACK-TEMPLATE.md` when claiming success.

## Post-pilot #1 adapter (explicitly out of v1)

**COS Seal / Portal Agent Registry** (`chief-of-staff` + versioned Agent Registry
with invocation grants) is the **#1 named follow-on** after pilot success. It
requires Nostr identities + ACP/`buzz-cli` bridge that honors portal grants —
not config-only.

## Mission Control note

MC Hub MCP routing from Cloud Agents may still return fuzzy portal-scoped
candidates for `local-inference` work. Prefer
`bash scripts/mc-checkout-local-inference.sh TASK-NNN` (or scoped compliance
checkout) when stamping PRs that touch this repo.
