# Claude Code — Local Inference

Thin adapter. Canonical agent entry is [`AGENTS.md`](AGENTS.md). Governance
pointer: [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) → `petralabx/PLX_MC`.

## What this repo is

spark-b4ec LiteLLM proxy + vLLM backends and DGX Spark GLM tooling. Clients call the
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

## Smoke

```bash
# From a machine on the tailnet (adjust if proxy host moves)
curl -sS http://100.92.253.61:4000/v1/models | head
```
