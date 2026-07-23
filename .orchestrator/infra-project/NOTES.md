# PRJ-INFRA-PROJECT / BKT-HARDENING — execution notes

## MC desynchronization

This cloud-agent run had no Team MCP / `MC_MCP_API_KEY` (JIT environment,
`environment: null`). Could not `mc_search_tasks`, `mc_checkout_task`, or
`mc_complete_task` for TASK-611..TASK-617. Proceeded per AGENT-PR-SOP fallback:
safe in-scope work from repository + fleet runbook context; reconcile MC when
credentials return. **Do not invent checkout stamps.**

## Assumed deliverables (repo gap audit → seven items)

Mapped to the seven backlog follow-ups by sequential hardening gaps observed in
`petralabx/local-inference` against tooling-tier / routing-activation requirements.
Re-read MC task titles when MCP is available and adjust if titles differ.

| Gap | Deliverable |
|-----|-------------|
| 1 | `.github/workflows/mc-routing-metadata.yml` (scaffold --routing-only) |
| 2 | `.github/plx-mc-routing-manifest.json` (descriptor → local-inference) |
| 3 | `.plx/mc-routing.json` |
| 4 | `.cursor/skills/` plx-engineering-core pack (from open PR #8 snapshot) |
| 5 | `CONTRIBUTING.md` petralabx/PLX_MC links + routing/welcome + validation cmds |
| 6 | `.github/workflows/ci.yml` unit tests + brand structure check |
| 7 | `docs/runbooks/control-plane-boundaries.md` tooling compliance surface |

Also fixed stale Hermes LAN IP in `docs/HERMES_PROVIDER.md`.

## Out of agent scope (operator)

- Org/repo Actions variable confirmation for routing enablement
- Live routing health proof + kill-switch replay (post-merge)
- PLX_MC `config/routing-pilots/local-inference.json` activation status flip
- MC task checkout/complete for TASK-611..617
