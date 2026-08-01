# AGENTS.md — Local Inference

Platform repo under PLX MC governance. Link work to MC tasks (`MC-Checkout`).

## Repo Topology (dev -> promote)

Two remotes carry this codebase with unrelated git histories:

- Dev / working repo: `taylorvalton/local-inference-dev` — day-to-day changes land here first.
- Canonical / PLX org repo: [petralabx/local-inference](https://github.com/petralabx/local-inference) —
  the MC-registered source of truth. Receives promotion PRs from the dev repo.

### Promotion workflow

1. Develop and merge changes on `taylorvalton/local-inference-dev` `main`.
2. When stable, copy the changed tracked files into the PLX checkout
   (histories are unrelated — promote by file copy, not by merging branches).
3. Open a `feat/promote-*` PR on `petralabx/local-inference`, referencing the
   dev-repo commits it promotes.
4. After merge, verify both repos' `main` trees match for the promoted paths.

### Rules

- Do not merge or rebase across the two remotes; they have unrelated roots.
- Secrets (`.env.local`) stay untracked in both repos.
- `.orchestrator/` evidence is promoted intentionally, not by default.

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
siblings. For automatic sibling checkouts (dev + canonical + PLX_MC):

1. Open [Cloud Agents → Environments](https://cursor.com/dashboard/cloud-agents#environments).
2. Create / edit an environment and select
   `petralabx/local-inference`, `taylorvalton/local-inference-dev`, and any
   other needed repos.
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
