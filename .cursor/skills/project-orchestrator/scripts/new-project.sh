#!/usr/bin/env bash
#
# new-project.sh — scaffold a Project Orchestrator spec.
#
# Usage: new-project.sh <slug>
#
# Creates <repo>/.orchestrator/<slug>/SPEC.md from the template (idempotent: refuses
# to overwrite an existing spec). <repo> is the current git work tree, else $PWD.

set -euo pipefail

slug="${1:-}"
if [[ -z "$slug" ]]; then
  echo "usage: new-project.sh <slug>" >&2
  exit 64
fi
if [[ ! "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "error: slug must be lowercase letters/digits/hyphens: '$slug'" >&2
  exit 64
fi

if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then :; else root="$(pwd)"; fi
dir="${root}/.orchestrator/${slug}"
spec="${dir}/SPEC.md"

if [[ -e "$spec" ]]; then
  echo "error: spec already exists: $spec (refusing to overwrite)" >&2
  exit 73
fi

mkdir -p "$dir"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$spec" <<EOF
---
project: ${slug}
created: ${now}
status: draft
approved_by:
approved_at:
model_plan:
  planner:
  builder:
  mechanical:
  critic:
budget:
  max_parallel_phases: 3
  max_attempts_per_phase: 3
  time_budget_min: 0
---

# <Project Title>

## Mission
<one paragraph: what and why>

## Success Criteria
- [ ] <measurable, verifiable outcome>

## Scope
- In: <what's included>
- Non-goals: <explicitly excluded>

## Phases

### P1 — <title>
- deliverables: <what exists when done>
- depends_on: []
- owns: ["<glob this phase may write>"]
- forbidden: []
- acceptance: \`<command that must exit 0>\`
- role: builder
- competitive: false

## Risks & Rollback
- <risk> -> <mitigation / how to roll back>

## Worktree Plan
- base branch: proj/${slug}
- phase branches: proj/${slug}/phase-<k>-<name>
- integration branch: proj/${slug}/integration
- delivery: one integration PR for the whole project
EOF

echo "created $spec"
echo "next: fill it in, then run spec-validate.sh '$spec'"
