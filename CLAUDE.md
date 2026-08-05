# Claude Code — Local Inference

Thin adapter. Canonical agent entry is [`AGENTS.md`](AGENTS.md). Governance
pointer: [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) → `petralabx/PLX_MC`.

## What this repo is

Dell LiteLLM proxy + vLLM backends and DGX Spark GLM tooling. Clients call the
proxy (`local-primary` / `local-coder` / `local-glm52`), not raw `:8000`
backends. Details: [`README.md`](README.md).

## Roots to preserve

| Path | Role |
|------|------|
| `scripts/` | Operator automation and workers |
| `litellm/` | Proxy config and related domain root |
| `docs/` | Runbooks and governance pointer |
| `.cursor/` | Agent rules / hooks |

Do **not** rename these roots without a costed migration note (see
[REPO-ONBOARDING](https://github.com/petralabx/PLX_MC/blob/main/docs/runbooks/REPO-ONBOARDING.md)
engineering-root stability).

## Working contract

- Prefer the Tailscale proxy URL for cross-machine clients.
- Never commit secrets (`.env.local` stays untracked).
- Develop on feature branches in `petralabx/local-inference`; never push
  directly to `main`.
- Treat `taylorvalton/local-inference-dev` as read-only legacy history. Audit
  and copy any unique tracked files through a normal canonical PR; never merge
  or rebase the unrelated histories.
- Agent PRs on the tracked canonical repo need `MC-Checkout: dsp_…` with
  `meta.actor.repo == petralabx/local-inference` (see
  `.cursor/rules/mc-compliance-gate.mdc` and PLX_MC AGENT-PR-SOP). Portal/Hub
  MCP stamps are wrong-scope here — use
  `bash scripts/mc-checkout-local-inference.sh TASK-NNN`.
- Day-to-day PR discipline: PLX_MC `COLLABORATOR-SOP.md`. Fleet onboarding /
  tier checklist: PLX_MC `REPO-ONBOARDING.md`.

## Smoke

```bash
# From a machine on the tailnet (adjust if proxy host moves)
curl -sS http://100.103.33.54:4000/v1/models | head
```
