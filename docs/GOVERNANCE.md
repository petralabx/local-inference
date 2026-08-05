# Governance pointer

This repository is a **PLX-tracked repo** (`tier: tooling` in
`PLX_MC/config/tracked-repos-registry.json`).

Canonical GitHub and active development repository:
**`petralabx/local-inference`**. The former
**`taylorvalton/local-inference-dev`** repository is legacy and receives no new
work; see `AGENTS.md` for the audited file-copy retirement rule.
Mission Control hub: **`petralabx/PLX_MC`** · cockpit:
[https://mc.plxcustomer.io](https://mc.plxcustomer.io)

| Document | Canonical location |
|----------|-------------------|
| Governance contract (SSOT) | [PLX_MC/config/governance-contract.yaml](https://github.com/petralabx/PLX_MC/blob/main/config/governance-contract.yaml) |
| Collaborator / PR SOP | [PLX_MC/docs/COLLABORATOR-SOP.md](https://github.com/petralabx/PLX_MC/blob/main/docs/COLLABORATOR-SOP.md) |
| Agent PR & MC-Checkout | [PLX_MC/docs/AGENT-PR-SOP.md](https://github.com/petralabx/PLX_MC/blob/main/docs/AGENT-PR-SOP.md) |
| Repo onboarding (fleet) | [PLX_MC/docs/runbooks/REPO-ONBOARDING.md](https://github.com/petralabx/PLX_MC/blob/main/docs/runbooks/REPO-ONBOARDING.md) |
| Fleet registry | [PLX_MC/config/tracked-repos-registry.json](https://github.com/petralabx/PLX_MC/blob/main/config/tracked-repos-registry.json) |

**Do not duplicate** full agent pillars or the entire MC-Checkout SOP in this
repo — those stay in PLX_MC. Exception: keep the thin always-applied operational
guard in `.cursor/rules/mc-compliance-gate.mdc` (repo slug handshake + Portal
MCP wrong-scope failure mode). Repo-specific workflow: `CONTRIBUTING.md`. Agent
entry: `AGENTS.md`. Claude adapter: `CLAUDE.md`.

Integration branch: `main`. Tier: `tooling`.
