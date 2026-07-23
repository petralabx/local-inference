---
name: plx-mc-workstation
description: >-
  Guides an agent when provisioning a new PLX Windows workstation or completing
  that workstation's first governed pull request. Use for workstation setup,
  PLX-MC access validation, repository bootstrap, and first-PR governance.
---

# PLX-MC Workstation

PLX_MC SOPs are canonical. This skill is only an execution checklist. If it
conflicts with a referenced SOP, stop and follow the SOP.

## 1. Verify prerequisites

- [ ] Confirm Windows PowerShell, Git, `gh`, Node.js, and Python are installed.
- [ ] Confirm access to the operator-approved AWS and GitHub accounts.
- [ ] Never print, echo, log, or paste secrets into chat, commits, PRs, or evidence.

Hydrate secrets from AWS:

```powershell
python scripts/bootstrap-windows-secrets.py
. $HOME\.secrets-env.github.ps1
# Or, when staging credentials are needed:
. $HOME\.secrets-env.staging.ps1
```

Stop if hydration fails or required credentials remain unavailable. Do not
invent, hardcode, or request secrets in plaintext.

## 2. Enable and validate PLX-MC MCP

PLX-MC MCP is disabled in committed configuration by default.

- [ ] Obtain explicit operator authorization before enabling it locally.
- [ ] Follow PLX_MC `docs/runbooks/plx-mc-mcp-team-registration.md`.
- [ ] Follow PLX_MC `docs/FLEET-SECRETS-SOP.md`.
- [ ] Account for `MC_MCP_API_KEY`, the operator email, and the current repository slug.
- [ ] Run `mc_self_check` and verify the reported operator and repository identity.

Do not duplicate or improvise MCP setup details from the canonical documents.

Stop if self-check fails, the identity is wrong, or the MCP remains disabled.
Do not continue governed task operations with an uncertain identity.

## 3. Validate the organization PAT

- [ ] Prefer `PETRALABX_GITHUB_TOKEN` over legacy `GITHUB_TOKEN`.
- [ ] Follow PLX_MC `docs/runbooks/petralabx-github-token-workstation.md`.
- [ ] Validate access without displaying token values.

Stop on authentication, organization-access, or repository-scope failure. Do
not replace the organization PAT with an unapproved weaker token.

## 4. Bootstrap the repository

- [ ] Clone only the operator-approved repository.
- [ ] Read its `AGENTS.md`, contributor guidance, and setup documentation.
- [ ] Use the repository's declared integration branch:
  - Portal repositories: `staging`.
  - PLX_MC and most tooling repositories: `main`.
  - Repository-specific policy overrides these defaults.
- [ ] Install dependencies using the repository's documented commands.
- [ ] Confirm the working tree and active worktree belong to this task.

Do not switch, stash, reset, rebase, delete, or otherwise mutate another
worktree.

Stop if the repository, remote, branch, or worktree identity is uncertain.

## 5. Start the first governed task

- [ ] Run `mc_self_check`.
- [ ] Search for the relevant task before creating one.
- [ ] Confirm the correct project, bucket, accountable owner, and repository identity.
- [ ] Create a task only when no suitable task exists.
- [ ] Check out the task under the current repository identity.
- [ ] Capture the exact returned stamp: `MC-Checkout: dsp_*`.

Stop if the task is in the wrong bucket, lacks an accountable owner, or was
checked out under the wrong repository identity. Never fabricate or manually
alter a checkout ID.

## 6. Implement and verify

- [ ] Keep changes limited to the checked-out task.
- [ ] Follow repository architecture, testing, and evidence requirements.
- [ ] Run relevant tests during implementation.
- [ ] Run the repository's canonical pre-commit gate before committing.
- [ ] Run the canonical pre-push gate before every push.
- [ ] Record exit-zero evidence without exposing secrets.

Stop on failing tests, gates, unexpected tracked-file mutations, or unresolved
compliance errors. Never bypass hooks, checks, or governance workflows.

## 7. Open and babysit the PR

- [ ] Target the repository's approved integration branch.
- [ ] Include the exact `MC-Checkout: dsp_*` stamp.
- [ ] Include a clear summary, verification evidence, and rollback plan.
- [ ] Include required task, PRD, or artifact links.
- [ ] Watch checks and reviews until resolved.
- [ ] Address review findings and rerun affected local gates.
- [ ] Merge only when required checks and approvals are green.

Do not push or merge to a production branch or `main` without explicit operator
approval, even when `main` is the repository's normal integration branch.

## 8. Close out safely

- [ ] Confirm the hosting provider reports the PR merged.
- [ ] Verify target-branch CI is green.
- [ ] When deployment applies, verify the intended commit, environment, deployment, domain, and live behavior.
- [ ] Complete the MC task with PR and verification evidence.
- [ ] Confirm any deferred work has its own governed task.
- [ ] Clean up the feature branch and worktree only after merge and verification.
- [ ] Leave unrelated worktrees untouched.

Stop if CI or deployment is failing, task evidence is incomplete, or cleanup
could destroy uncommitted work.

## 9. Handle cross-repository work

For every repository involved:

- [ ] Set and validate that repository's identity independently.
- [ ] Search, create if needed, and check out a separate MC task.
- [ ] Use the checkout stamp returned for that repository only.
- [ ] Attach repository-specific evidence before completing its task.

Never reuse a checkout ID across repositories.

## Guardrails

- Never hardcode or expose secrets.
- Never bypass compliance, hooks, checks, or approvals.
- Never push or merge to production or `main` without operator approval.
- Do not install routing activation workflows in this skill.
- Do not change `PLX_MC_ROUTING_METADATA_ENABLED`.
- Do not use confirmation probes or fuzzy matching to activate routing.
- Do not treat MCP availability as authorization.
- Fail visibly whenever identity, authorization, evidence, or state is uncertain.

## Canonical references

Read the applicable PLX_MC documents before execution:

- `docs/runbooks/REPO-ONBOARDING.md`
- `docs/COLLABORATOR-SOP.md`
- `docs/AGENT-PR-SOP.md`
- `docs/runbooks/plx-mc-mcp-team-registration.md`
- `docs/FLEET-SECRETS-SOP.md`
- `docs/runbooks/petralabx-github-token-workstation.md`
- `docs/runbooks/mc-routing-rollout.md`

These PLX_MC SOPs remain the source of truth; this skill does not replace them.
