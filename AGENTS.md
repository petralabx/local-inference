# AGENTS.md — Local Inference

Platform repo under PLX MC governance. Link work to MC tasks (`MC-Checkout`).

## Mission Control handshake (Claude Code and every agent)

<!-- plx-mc:handshake:start -->
Generated from PLX_MC [`config/governance-contract.yaml`](https://github.com/petralabx/PLX_MC/blob/main/config/governance-contract.yaml) by `scripts/generate-governance-surfaces.py --fleet`. Do not edit this block: change the contract and regenerate.

Before the first edit or any PR on `petralabx/local-inference`:

1. Search projects, buckets and TASK-* first (mc_search_tasks: branch, title, runId). Create a task only on a real miss, with mc_create_task in BKT-INFRA. Never create a task to escape incomplete evidence on a live checkout.
2. Check out with mc_checkout_task, passing repo `petralabx/local-inference`, your own `runtime/lane` as agent, and your branch. Confirm the returned taskId and that actor.repo is `petralabx/local-inference`. Copy prBodyLine exactly.
3. Never invent a dsp_* id, never write `MC-Checkout: pending`, and never push with --no-verify. Without the MC tools, check out over HTTP: `COMPLIANCE_CAPTURE=1 MC_REPO=petralabx/local-inference MC_TASK_ID=TASK-N node scripts/compliance-checkout.mjs`. If that fails too, stop and ask CoS or CIP to paste the prBodyLine.
4. End every commit with Agent, On-Behalf-Of and MC-Checkout as its last three lines. Name the TASK id in the PR title or branch.
5. Save evidence with mc_save_evidence before you open the PR, and put the MC-Checkout line in the PR body when you open it.
6. After you fix a PR body, re-run the failed compliance job. Never push an empty commit, and never close and reopen a PR, to restart a check.
7. After the last commit, call mc_complete_task with verificationCommands, rollback and the PR link. Then move the task's stage, or say why you cannot.
8. Mark a green PR ready and stop: only CIP's merge-queue session arms auto-merge or merges, with a merge commit into `main`. A PR that touches money, migrations or workflows, or reverts merged work, needs a signed MC merge approval of its exact head (mc_request_approval, merge scope).

- A plan that adds a project, or two or more buckets, goes through a draft: mc_save_draft, then mc_submit_draft. Its author accepts it in Mission Control.
<!-- plx-mc:handshake:end -->

## Workstream protocol

Sessions are disposable. What the next session or a teammate needs lives in
[`docs/workstreams/`](docs/workstreams/README.md) and travels with the code (Vince, 2026-10-26, TASK-3953).

- One workstream per branch and worktree. Flag any edit outside your workstream's scope before you make it. A one-PR change needs no workstream.
- At session start, read your workstream's note, `docs/workstreams/<slug>.md`. The index in `docs/workstreams/README.md` maps branches to slugs.
- Before you end a session, and after any significant decision, update that note in the same branch (`/handoff` in Claude Code and Cursor; `/resume-workstream` picks it up).
- Change the index row (owner, branch, status, dependencies) only when a workstream opens, closes or changes status.
- SharePoint `Agent Handoffs/` stays the system of record for durable handoffs. The note is the agents' working copy; when they disagree, SharePoint wins.

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
  at `http://100.92.253.61:4000/v1` via the request-scoped userspace proxy
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
is the operator mesh: the spark-b4ec LiteLLM proxy, the DGX Sparks, and the AWS
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
