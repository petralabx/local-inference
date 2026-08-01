---
name: safe-deletion
description: Remove files, symbols, modules, or dependencies safely so deletions are verified before commit and never break transitive consumers. Use when deleting code confirmed unused (e.g. by the dead-code-triage skill), removing a dependency, collapsing a module, or retiring a deprecation shim.
---

# Safe Deletion

Deletion is a change with a blast radius. This skill makes removals verifiable and
reversible. Use it after `dead-code-triage` has confirmed a candidate is truly
unused. Apply the universal workflow below in **any** repo; for agentic-swarm / VMC
governance gates and manifests, see [reference.md](reference.md).

## Universal Toolkit

| Tool | When to Use |
|------|-------------|
| `rg` (ripgrep) | Find every reference to the deletion target |
| Language-native typecheck | Catch breakage from removed exports/symbols |
| Language-native test slice | Confirm nothing downstream broke |
| `git rm` + a single focused commit | Keep deletions reversible via revert |

## Pre-Deletion Checklist

### 1. Blast Radius
Know what depends on the target before touching it. List the modules/files that
import it. If anything critical or widely-depended-on is in scope, write a one-line
rollback plan (which commit/flag restores it) before proceeding.

### 2. Reference Elimination
Confirm zero remaining references — **remove references first, delete last**:
```bash
rg "targetSymbol" .                                      # code, config, docs
rg "import\(.*targetSymbol|require\(.*targetSymbol" .     # dynamic references
rg "targetSymbol" config/ docs/ .cursor/                 # string-form references
```
Never delete a definition while references still exist.

### 3. Barrel / Index Cleanup
If the target was re-exported from a barrel/index:
1. Remove the re-export line.
2. Re-run typecheck to confirm no consumer broke.
If an entire barrel directory is going away, check for a deprecation shim at the old
path first — if a shim exists and hasn't expired, update its target instead of deleting.

### 4. Dependency Cleanup
If you removed the last consumer of a dependency, remove the dependency too, from
**all** manifests (e.g. `requirements.txt` + `pyproject.toml`, or `package.json` +
lockfile), then re-resolve to confirm nothing else needed it.

### 5. Manifest / Config Cleanup
Remove the target from any registry that names files or symbols (module manifests,
skill/agent/pipeline configs, ownership maps) and run that registry's validator.

## Post-Deletion Verification
Run in order; stop and fix on the first failure:
```bash
# 1. Typecheck (if typed files changed)
# 2. Affected test slice
# 3. Repo boundary / governance checks (see reference.md in this repo)
# 4. Full local CI before push
```

## Deletion Patterns

**Single symbol** — remove definition → remove all imports → remove barrel
re-export → typecheck + quick test.

**Whole file** — remove all imports repo-wide → remove barrel re-export → remove
from any manifest → delete file → full check.

**Module directory** — check for shims pointing in → remove all external imports
(use the blast radius) → remove from manifests/config → delete → full check +
governance.

**Deprecate instead of delete** (when immediate removal is risky) — leave a shim at
the old path that re-exports the new location, annotate it with a dated removal
banner, and add a removal task with the expiry date:
```text
// module-shim — remove after YYYY-MM-DD
// DEPRECATED SHIM — do not add new imports to this file
```

## When NOT to Delete
- The file carries an unexpired deprecation-shim banner.
- It's a framework entry point (route/handler/lifecycle export) — looks unused, isn't.
- It's referenced only by test fixtures (removal breaks test infrastructure).
- It was added in an open, unmerged PR.
- The blast radius is large/critical and there's no reviewed rollback plan.

## Repo-specific playbook
For agentic-swarm / VMC — `check-change-impact.py`, `check-vmc-boundaries.py`,
`check-api-governance.py`, `ci-local.sh`, the module manifest, and skill/agent/pipeline
config cleanup — see [reference.md](reference.md).
