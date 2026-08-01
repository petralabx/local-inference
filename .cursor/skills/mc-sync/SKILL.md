---
name: mc-sync
description: Keep agent sessions aligned with PLX Mission Control tasks via the PLX-MC MCP server — checkout, progress, and complete with evidence. Use when working PLX MC tasks or when the user references Mission Control dispatch IDs.
---

# PLX MC Sync (Cursor agents)

Keep agent sessions aligned with PLX Mission Control tasks via the **PLX-MC** MCP server.

## Lifecycle

1. **Checkout** — `mc_checkout_task` before starting work. Copy `MC-Checkout: dsp_*` from the response into the PR body.
2. **Progress** — `mc_report_progress` at milestones (~every 10–15 min).
3. **Complete** — `mc_complete_task` with evidence (summary, commit SHA, PR URL, verification commands).

## Enable

Set in `.cursor/mcp.json` (or team MCP at cursor.com/agents):

- `PLX_MC_MCP_ENABLED=1`
- `MC_MCP_API_KEY`, `MC_OPERATOR_EMAIL`, `MC_REPO`
- `MC_BASE_URL=https://mc.plxcustomer.io`

## Fallback (capture hook)

```bash
COMPLIANCE_CAPTURE=1 MC_MCP_API_KEY=... MC_OPERATOR_EMAIL=... MC_REPO=... MC_BASE_URL=... node scripts/compliance-checkout.mjs
```

## Remote HTTP MCP

`https://mc.plxcustomer.io/api/cursor/mcp` — see `docs/runbooks/plx-mc-mcp-team-registration.md`.
