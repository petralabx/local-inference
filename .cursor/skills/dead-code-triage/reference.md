# Dead Code Triage — agentic-swarm / VMC playbook

Repo-specific scanners, reports, and false-positive patterns. Use only in the
agentic-swarm / VMC working tree. Universal logic lives in [SKILL.md](SKILL.md).

## Repo tools

| Tool | When to Use |
|------|-------------|
| `scripts/code-health-scan.sh --quick` | Generate a fresh unused-candidates report |
| `vmc_get_unused_candidates` (MCP) | Read cached dead-code candidates |
| `python scripts/check-change-impact.py` | Assess blast radius of removing a file/symbol |
| `vulture src/ --min-confidence 80` | Python dead-code scan (standalone) |
| `cd apps/vmc-web && npx knip --reporter json` | TypeScript unused exports/files scan |

## Generate candidates

```bash
scripts/code-health-scan.sh --quick
cat data/reports/code-health/unused-candidates.json | jq '.candidates | length'
```

Each candidate includes: file path, symbol name, confidence score, and source tool.

## Blast radius for a candidate

```bash
python scripts/check-change-impact.py <(echo "path/to/file")
```
If the candidate is under `lib/vmc/*/`, check whether `index.ts` re-exports it
before trusting any "unused" verdict.

## Known false positives in this repo

- **Next.js route handlers** — exported `GET`/`POST` are framework entry points, never imported.
- **Barrel re-exports** — `index.ts` re-exports consumed via the barrel path.
- **LangChain tools** — `@tool`-decorated; called by the framework at runtime.
- **Pipeline steps** — registered in `config/pipelines.yaml`, invoked by name.
- **Agent tools** — registered in `config/agents.yaml` `tools:` arrays.
- **CSS custom properties** — referenced via `var(--token)` in templates.
- **Shims** — files marked `// module-shim — remove after YYYY-MM-DD` are intentionally deprecated, not dead.

## Repo-aware verification additions

```bash
# Config references specific to this repo
rg "symbolName" config/ apps/vmc-web/src/data/ .cursor/
# Agent tool-bundle registration
rg "symbolName" config/agents.yaml config/pipelines.yaml
# Test references
rg "symbolName" tests/ apps/vmc-web/src/lib/vmc/__tests__/
```

## Fallback (no MCP)

```bash
vulture src/ --min-confidence 80
cd apps/vmc-web && npx knip --reporter json
rg "myFunction" --type-add 'all:*' -t all .
```
