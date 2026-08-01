---
name: worktree-bootstrap
description: >-
  Bootstrap a freshly created git worktree so it is actually runnable, and avoid
  the cross-platform pitfalls that break worktrees. Use right after
  `git worktree add`, when opening or being pointed at a new worktree, or when a
  fresh worktree fails to run because untracked / gitignored artifacts are
  missing (node_modules, generated clients like Prisma, .venv, submodule
  contents). Also covers the PowerShell `$Args` parameter-splatting footgun, the
  Windows background-shell cwd / ENOENT bug, and worktree cleanup after merge.
---

# Worktree Bootstrap

Git worktrees share `.git` history but **not** untracked / gitignored artifacts
(dependencies, generated code, build caches, virtualenvs, submodule contents). A
freshly created worktree is therefore **not runnable until it is bootstrapped.**

## When

- Right after `git worktree add ...`, or when opened / pointed at a fresh worktree.
- When a new worktree fails to run (missing `node_modules`, a generated client,
  `.venv`, or empty submodules).

Do this **proactively** — don't ask first.

## Bootstrap

1. **Prefer the repo's own bootstrap script** if one exists, e.g.
   `scripts/bootstrap-worktree.*`, `make bootstrap`, `./bin/setup`, or a
   `bootstrap` / `setup` package script. Run it in the **foreground**; it is
   usually idempotent (safe to re-run).
2. **Otherwise bootstrap manually** for whatever the repo uses:
   - **Node**: install with the repo's manager (`npm ci`, `pnpm i --frozen-lockfile`,
     `yarn install --immutable`); run any codegen (`prisma generate`, GraphQL, etc.).
   - **Python**: create the venv and install (`python -m venv .venv` +
     `pip install -r requirements.txt`, or `uv sync` / `poetry install`).
   - **Submodules**: `git submodule update --init --recursive`.
   - Recreate any gitignored local config the repo expects (`.env`, secrets) per
     its docs.
3. **Verify** it runs (build / typecheck / test, or start the dev server) before
   working in it.

## Branch base

Branch a new worktree off the repo's integration branch (e.g. `main` / `staging`),
never a production branch, unless explicitly told otherwise.

## Cross-platform pitfalls (these have bitten before)

### PowerShell `$Args` parameter collision

Never name a function parameter `$Args` — it collides with PowerShell's automatic
`$Args` variable, so splatting `@Args` passes **zero** arguments and the native
command runs bare (e.g. `npm` prints its usage banner and exits 1, "failing"
bootstrap for no obvious reason). Use a non-reserved name such as `$Arguments`.

### Windows background-shell cwd / ENOENT

Backgrounded shells may resolve a *relative* working directory against the
editor's install dir instead of the repo, dying instantly with a misleading
`spawn ... ENOENT`. Run long bootstrap commands (installs / builds) in the
**foreground** with a generous timeout, or pass an **absolute** working
directory; then sanity-check the terminal output.

### Multi-line inline eval snippets

`node -e` / `tsx -e` (or any inline snippet) with literal newlines drops
PowerShell into a `>>` continuation prompt that hangs forever. Use a single line,
or write a temp `.mjs` / `.ps1` file and run that.

## Cleanup (after the worktree's work is merged)

Remove the worktree (`git worktree remove <path>`, add `--force` if it has
installed artifacts), run `git worktree prune`, and delete the merged branch
(local + remote). On Windows the directory delete can hit a file lock — retry
once the editor / process releases the handle.
