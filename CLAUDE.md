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
  `.cursor/rules/mc-compliance-gate.mdc` and PLX_MC AGENT-PR-SOP). A Hub stamp
  is right-scope only when `actor.repo == petralabx/local-inference` (pass
  `repo=` or use this repo's `.mcp.json`). Use
  `bash scripts/mc-checkout-local-inference.sh TASK-NNN`.
- Day-to-day PR discipline: PLX_MC `COLLABORATOR-SOP.md`. Fleet onboarding /
  tier checklist: PLX_MC `REPO-ONBOARDING.md`.

## Mission Control handshake (Claude Code and every agent)

Before first edit or any PR_CREATE on `petralabx/local-inference`:

1. **Search** projects, buckets and TASK-* first (`mc_search_tasks` / `mc_suggest_work`: branch, title, runId). Reuse a matching open TASK.
2. **Create only on a real miss**: `mc_create_task` in the registry default bucket (`BKT-INFRA`, from PLX_MC `config/tracked-repos-registry.json`; do not hardcode another prod bucket). Create a project/bucket only if it is truly missing. Never create a TASK to escape incomplete evidence on a live checkout.
3. **Checkout**: `mc_checkout_task { taskId, repo: "petralabx/local-inference" }` on PLX-MC-Hub. Confirm `taskId` matches and `actor.repo` is `petralabx/local-inference`. Copy `prBodyLine` exactly. HTTP fallback when Hub MCP tools are missing:
   `COMPLIANCE_CAPTURE=1 MC_REPO=petralabx/local-inference MC_TASK_ID=TASK-N node scripts/compliance-checkout.mjs` (reads `MC_BASE_URL`, `MC_MCP_API_KEY`, `MC_OPERATOR_EMAIL`, `MC_ACCOUNTABLE` from the environment; never echo the key).
   Preferred scoped fallback here: `MC_RUNTIME=claude-code bash scripts/mc-checkout-local-inference.sh TASK-NNN`.
4. **Stamp at PR open**: put the `MC-Checkout: dsp_…` line in the body at `gh pr create` time (the compliance gate reads the body on opened/synchronize/reopened only, not on edits). Never invent a `dsp_*`, never write `MC-Checkout: pending`, never `--no-verify`, never an empty commit or push to re-trigger CI. If the body must change after open, ask CIP to close/reopen.
5. **Last commit → `mc_complete_task`** (summary + verificationCommands + rollback) **→ freeze**. CIP lands; agents never merge. Next slice = new branch from the integration branch.
6. If Hub MCP and the HTTP fallback both fail: stop; CoS/CIP paste `prBodyLine`.

## Smoke

```bash
# From a machine on the tailnet (adjust if proxy host moves)
curl -sS http://100.103.33.54:4000/v1/models | head
```
