---
name: worktree-open-session
description: >-
  Create an isolated git worktree off staging for PLX portal work, bootstrap it,
  open a new Cursor window, and paste the project's PASTE-FIRST or KICKOFF
  prompt. Use when Vince asks for a new worktree/window for a project slug
  (UAT loop, PD pipeline, quote module, etc.).
---

# Worktree Open Session

Compose **worktree create + bootstrap + session start**. For bootstrap-only
(already-created worktree), use **worktree-bootstrap**.

## Preferences

- Base: `staging` unless Vince names another branch
- Path pattern: `~/.cursor/PLXPORTAL/plx-customer-portal-<slug>` (or Vince path)
- Branch: `proj/<slug>` or Vince-specified
- Bootstrap immediately — do **not** ask first:
  `scripts/bootstrap-worktree.ps1` (+ `-WithSwarm -WithVenv` if Python/swarm)
- First message: project's `.orchestrator/<slug>/PASTE-FIRST.md` or `KICKOFF.md`
  when present
- Do not stash / switch / delete other worktrees unless Vince asked
- Windows: run long installs in the **foreground** persistent shell (cwd bug)

## Steps

1. From the main portal clone: `git fetch origin`
2. `git worktree add -b <branch> <abs-path> origin/staging`
3. In that path, run bootstrap in foreground (budget minutes for `npm ci`)
4. Open a new Cursor window on `<abs-path>` (IDE command or clear manual instruction)
5. Leave the PASTE-FIRST / KICKOFF block ready as the first agent message
6. Confirm: branch name, tracking remote, bootstrap status, secrets reminder

## Done when

- [ ] Worktree exists at the agreed path
- [ ] Bootstrap completed (or idempotent skip confirmed)
- [ ] New window opened **or** explicit open instructions given
- [ ] First-paste prompt identified (path + summary)
- [ ] No unintended stash/branch changes in other worktrees

## Related

- Bootstrap details / Windows pitfalls: `worktree-bootstrap`
- UAT weekly kickoff example: portal `.orchestrator/uat-weekly-batch-loop/`
