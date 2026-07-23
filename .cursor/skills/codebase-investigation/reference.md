# Codebase Investigation — agentic-swarm / VMC playbook

Repo-specific commands and conventions. Use these only when the working tree is
the agentic-swarm / VMC repo. The universal lifecycle lives in [SKILL.md](SKILL.md).

## Repo tools

| Tool | When to Use |
|------|-------------|
| `python scripts/check-change-impact.py` | Map a file to its owning module and blast radius |
| `scripts/ci-local.sh --quick` | Fast verification that changes haven't broken anything (~15s) |
| `scripts/ci-local.sh` | Full local pipeline (~60s) before push |
| `vmc_get_repo_health` (MCP) | Cached repo health summary before deep investigation |

## Module ownership and blast radius

- Module ownership and `depended_on_by` edges: `docs/modules/modules.manifest.json`.
- Map recently changed files to their blast radius first — it often points straight
  at the source:
  ```bash
  python scripts/check-change-impact.py <(echo "path/to/file.ts")
  git diff --name-only | python scripts/check-change-impact.py -
  ```

## Tracing by issue type

**API / request issues**
1. Find the route: `rg "api/vmc/<path>" apps/vmc-web/src/app/api/`
2. Read the route handler — note which store functions it calls.
3. Follow store imports **through barrel `index.ts` files** (never bypass barrels).
4. Check the DB query or external call at the edge.

**Agent / swarm issues**
1. Find the agent config: `rg "<agent_name>" config/agents.yaml`
2. Read the prompt file referenced in the config.
3. Check tool bindings in `src/tools/`.
4. Trace the team graph in `src/teams/`.

**Cross-module issues**
1. Use `docs/modules/modules.manifest.json` to find `depended_on_by` edges.
2. Search for imports of the affected module's barrel.
3. Check for shims that redirect imports: `rg "module-shim" src/ apps/`.

## Verify

```bash
scripts/ci-local.sh --quick                 # known-good baseline
npm run typecheck --prefix apps/vmc-web      # if VMC TS was touched
```

Cross-reference `LESSONS.md` before reporting — avoid re-deriving known issues.

## Fallback (no semantic search / no MCP)

```bash
# All callers of a function (TS/TSX)
rg "functionName\(" --type-add 'ts:*.{ts,tsx}' -t ts apps/vmc-web/src/

# All files importing a module barrel
rg "from ['\"]@/lib/vmc/moduleName" apps/vmc-web/src/

# Module ownership for one file
python scripts/check-change-impact.py <(echo "path/to/file.ts")

# Recent history for a file
git log --oneline -20 -- path/to/file.ts
```
