# Safe Deletion — agentic-swarm / VMC playbook

Repo-specific governance gates and manifests. Use only in the agentic-swarm / VMC
working tree. Universal workflow lives in [SKILL.md](SKILL.md).

## Repo tools

| Tool | When to Use |
|------|-------------|
| `python scripts/check-change-impact.py` | Map deletion targets to module blast radius |
| `python scripts/check-vmc-boundaries.py` | Verify no barrel bypass after removal |
| `python scripts/check-api-governance.py` | Verify API routes remain compliant |
| `scripts/ci-local.sh --quick` | Fast post-deletion verification |
| `scripts/ci-local.sh` | Full verification before push |
| `npm run typecheck --prefix apps/vmc-web` | Catch TS breakage from removed exports |

## Blast radius

```bash
python scripts/check-change-impact.py <(echo "path/to/target.ts")   # single file
git diff --name-only | python scripts/check-change-impact.py -        # staged set
```
If **Critical** modules are in the blast radius, document a rollback plan first
(this repo's rule: PR bodies touching critical modules need a `## Rollback Plan`).

## Manifest and config cleanup

Check whether the deleted file appears in any of these, and remove stale entries:
- `docs/modules/modules.manifest.json` (`key_files` arrays)
- `config/skills.yaml` (`file` field)
- `config/agents.yaml` (tool references)
- `config/pipelines.yaml` (step references)

Then run the validators:
```bash
python scripts/validate-modules-manifest.py
python scripts/check-skills-schema.py
```

## Post-deletion verification (full order)

```bash
scripts/ci-local.sh --quick                  # 1. quick smoke
npm run typecheck --prefix apps/vmc-web       # 2. TS check if VMC touched
python scripts/check-vmc-boundaries.py        # 3. boundary check
python scripts/check-api-governance.py        # 3. API governance
scripts/ci-local.sh                           # 4. full CI before push
```

## Deprecation shim (repo banner format)

```typescript
// module-shim — remove after YYYY-MM-DD
// DEPRECATED SHIM
// Do not add new imports to this file
export { target } from "@/lib/vmc/newLocation";
```
Add a removal task to `tasks/todo.md` with the expiry date. Shims are CI-checked
for expiry — an expired shim is a hard failure.

## Repo-specific "do not delete"

- Next.js route handlers (`GET`/`POST` exports are framework entry points).
- Files under an unexpired `// module-shim` banner.
- Anything still registered in `config/agents.yaml`, `config/pipelines.yaml`, or
  `config/skills.yaml`.
