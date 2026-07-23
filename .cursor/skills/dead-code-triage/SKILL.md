---
name: dead-code-triage
description: Classify suspected-unused code before deleting it, ruling out dynamic imports, framework entry points, barrel re-exports, and config/string references. Use when reviewing dead-code candidates from static analysis (vulture, knip, ts-prune, unused-exports) or manual inspection, to avoid false-positive deletions that break runtime behavior.
---

# Dead Code Triage

Static analyzers report *suspected* unused code. Many "unused" symbols are reached
dynamically, by a framework, or through a barrel — deleting them breaks runtime
with no compile error. This skill is the verification gate between "flagged" and
"safe to delete". Pair it with the `safe-deletion` skill for the actual removal.

Apply the universal classification below in **any** repo. For agentic-swarm / VMC
scanners, reports, and known false-positive patterns, see [reference.md](reference.md).

## Universal Toolkit

| Tool | When to Use |
|------|-------------|
| `rg` (ripgrep) | Search for dynamic/string/config references to a candidate |
| `vulture <pkg> --min-confidence 80` | Python dead-code scan |
| `npx knip` / `npx ts-prune` | TypeScript unused files/exports scan |
| `git log -S '<symbol>' --oneline` | See when/why the symbol was added |

## Triage Lifecycle

### 1. Gather Candidates
Each candidate should have: file path, symbol name, confidence, and source tool.
Triage highest-confidence, lowest-risk candidates first.

### 2. Classify Every Candidate
Sort each into exactly one bucket:

**TRUE POSITIVE — safe to delete**
- No callers found via `rg`; not referenced in config/YAML/JSON.
- Not imported dynamically; not part of a public API surface or barrel export.

**FALSE POSITIVE — dynamic / config reference**
- Reached via string interpolation, `import()`, `require()`, reflection, or `eval()`.
- Listed in config (`*.yaml`, `package.json`, `tsconfig.json`) or used as a CLI
  entry point, cron target, or pipeline step.

**FALSE POSITIVE — framework entry point / barrel re-export**
- Framework-invoked exports (e.g. route handlers, lifecycle hooks, DI-registered
  providers, decorated handlers) that are never imported directly.
- Re-exported from a barrel `index` while consumers import through the barrel — the
  tool flags the implementation file, but the barrel path is the real consumer.

**DEFERRED — needs more context**
- Part of a recently merged or in-flight feature; has tests that would break;
  owned by another module with possible out-of-tree consumers.

### 3. Verification Checklist (before any TRUE POSITIVE)
```bash
# 1. Any reference at all (code, comments, configs, docs)
rg "symbolName" --type-add 'all:*' -t all .
# 2. Dynamic import / require
rg "import\(.*symbolName|require\(.*symbolName" .
# 3. Config / data references
rg "symbolName" config/ **/data/ .cursor/ 2>/dev/null
# 4. Barrel re-export (if symbol lives under a module dir, check its index)
# 5. Test references
rg "symbolName" test/ tests/ **/__tests__/ 2>/dev/null
```
A symbol is TRUE POSITIVE only if **all** checks come back empty.

### 4. Batch the Decisions
- **Quick wins** — single-symbol removals with no transitive impact.
- **Module cleanups** — multiple symbols in one module, handled together.
- **Cross-module** — removals touching other modules' dependents; get owner review.

Hand the confirmed TRUE POSITIVE set to the `safe-deletion` skill.

## Universal False-Positive Patterns
- Framework route/handler exports (HTTP verbs, page/loader exports) — entry points.
- Barrel re-exports consumed via the barrel path.
- Reflection / DI / decorator-registered symbols invoked by name at runtime.
- Plugin or pipeline steps registered in config and invoked by string key.
- Style tokens / CSS custom properties referenced in templates, invisible to JS analysis.
- Intentional deprecation shims (annotated with a removal-date banner).

## Repo-specific playbook
For agentic-swarm / VMC — `scripts/code-health-scan.sh`, the `vmc_get_unused_candidates`
MCP tool, `data/reports/code-health/`, blast-radius mapping, and this repo's exact
false-positive patterns — see [reference.md](reference.md).
