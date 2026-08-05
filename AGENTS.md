# AGENTS.md — Local Inference

Platform repo under PLX MC governance. Link work to MC tasks (`MC-Checkout`).

## Repository Topology

[petralabx/local-inference](https://github.com/petralabx/local-inference) is the
only active development repository and the MC-registered source of truth.

1. Create a feature branch in this repository.
2. Develop and verify the change on that branch.
3. Open a pull request to `main`; never push directly to `main`.
4. Merge only after repository checks and MC compliance pass.

The former `taylorvalton/local-inference-dev` repository is legacy and must not
receive new work. Preserve its history until its tracked files, open pull
requests, and non-default branches have been audited. Copy any approved unique
files through a normal PR here; never merge or rebase the unrelated histories.

Secrets (`.env.local`) stay untracked. `.orchestrator/` evidence is committed
only when an approved delivery contract requires it.

## Cursor Cloud Agents

Committed config: `.cursor/environment.json`. On Cloud Agent start it runs
`scripts/setup_linux_venv.sh` (creates `.venv/`, installs `requirements.txt`).

### Session facts

- A running JIT agent (`environment=null`) **cannot** be re-attached to a saved
  environment. Start a **new** agent after this config lands on the default
  branch (or launch via API with `env.name`).
- Cloud VMs are Linux. Use `.venv/bin/...`, never Dell Windows `.venv/Scripts/`.
- Do not start Dell/DGX GPU backends in the cloud VM. Call the Tailscale proxy
  at `http://100.103.33.54:4000/v1` via the request-scoped userspace proxy
  `http://127.0.0.1:1054` — never set global `HTTP(S)_PROXY` / `ALL_PROXY`.
- Secrets (`LOCAL_LITELLM_MASTER_KEY`) belong in the dashboard environment
  Secrets tab, not in git.

### Multi-repo workspace (dashboard)

`repositoryDependencies` only expands GitHub token scope; it does **not** clone
siblings. For a workspace that also needs Mission Control source:

1. Open [Cloud Agents → Environments](https://cursor.com/dashboard/cloud-agents#environments).
2. Create / edit an environment and select `petralabx/local-inference`,
   `petralabx/PLX_MC`, and any other needed repos.
3. Save a snapshot after agent-driven setup if you want faster boots.
4. Start new agents against that repo group (UI) or
   `POST /v1/agents` with `env: { "type": "cloud", "name": "<exact name>" }`.

Committed `.cursor/environment.json` outranks personal/team saved envs for this
repo. Keep install lean here; put multi-root layout in the dashboard env.

## MC Compliance Gate (agent PRs)

Hard gate on this repo. Always-applied rule:
`.cursor/rules/mc-compliance-gate.mdc`. Fleet SSOT:
`petralabx/PLX_MC` (`scripts/compliance-pr-verify.mjs`, drift-checked here).

```bash
bash scripts/mc-checkout-local-inference.sh TASK-NNN   # scoped stamp
# ... work, stamp the PR, hand in evidence via mc_complete_task ...
MC_REPO=petralabx/local-inference node scripts/compliance-pr-verify.mjs --wait
```

`mc_complete_task` returning ok is **not** gate success (PR #11). Only GitHub
`compliance` SUCCESS / verify exit 0 is. Portal/Hub MCP stamps are wrong-scope
here (decision 3). Never invent stamps; never edit
`.github/workflows/*compliance*`.
