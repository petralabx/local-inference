---
name: wterm-preflight
description: Run the canonical local CI gate via scripts/wterm-preflight.sh before committing and pushing in the agentic-swarm / VMC repo (pre-commit fast gate, pre-push full gate). Use before any git commit or push in that repo. If scripts/wterm-preflight.sh is not present in the current repo, this skill does not apply — use that repo's own pre-commit checks instead.
---

# Wterm Preflight Gate Skill

Use this skill before **every** `git commit` and **every** `git push` **in the
agentic-swarm / VMC repo**. It standardizes local verification behind one command
for all coding agents.

> Scope guard: this skill targets repos that provide `scripts/wterm-preflight.sh`.
> If that script does not exist in the current working tree, do not invoke it — run
> the local repo's own lint/typecheck/test gate instead.

Reference project: [vercel-labs/wterm](https://github.com/vercel-labs/wterm)

## Canonical Commands

```bash
# Commit-time gate (fast)
./scripts/wterm-preflight.sh --mode pre-commit

# Push-time gate (full)
./scripts/wterm-preflight.sh --mode pre-push
```

## Required Behavior

1. Before creating a commit, run the pre-commit mode and only proceed on exit 0.
2. Before pushing a branch (including PR updates), run the pre-push mode and only proceed on exit 0.
3. If the gate fails, fix the issue first; do not bypass with `--no-verify`.

## Enforcement Surfaces

- Local git hook: `.pre-commit-config.yaml`
- Cursor shell guard: `scripts/cursor-hooks/before-shell.py`
- CI policy check: `.github/workflows/test.yml`

This skill is advisory by itself; the three enforcement surfaces above are mandatory.
