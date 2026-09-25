# AGENTS.md — Local Inference

Platform repo under PLX MC governance. Link work to MC tasks (`MC-Checkout`).

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

## Multi-device / Laptop ↔ Desktop Continuity

Sitting at Dell-VTA is the default seat: open Cursor and work. No extra
steps.

When you are on a laptop, the web, or a phone, use **My Machines** (worker
on Dell-VTA) plus Cloud Agents. Dell is the Cursor tool-call host. Compute
is the operator mesh: Dell LiteLLM proxy, the DGX Sparks, and the AWS
primitives already in that mesh. See `.cursor/rules/multi-device-cursor.mdc`
and `docs/runbooks/multi-device-cursor.md`.

- Chat history remains local and path-hash-bound. Do not rely on it for
  continuity.
- Keep this file, the always-applied rules, and the runbooks under
  `docs/runbooks/` as the durable context that any Cursor instance can
  rehydrate from.
- For long-running or hardware-dependent work (GPU, Tailscale proxy, Docker
  on Dell, Spark backends), prefer the worker on Dell rather than a pure
  cloud VM. Do not start GPU backends inside a Cloud Agent VM.
- After landing changes to `.cursor/environment.json` or install scripts,
  start a fresh Cloud Agent. Existing JIT sessions cannot re-attach.

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
