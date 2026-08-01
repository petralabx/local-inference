#!/usr/bin/env bash
# vmc-autoresearch-core — eval/ scaffold generator
#
# Usage: init-eval.sh <domain> <worktree-path>
#   domain:        one of: chat | swarm | todos | second-brain
#   worktree-path: absolute path to the autoresearch/<domain> worktree
#
# Creates the canonical eval/ directory structure per
# .cursor/skills/vmc-autoresearch-core/reference.md §2.
# Idempotent: refuses to overwrite existing files.

set -euo pipefail

DOMAIN="${1:-}"
WORKTREE="${2:-}"

if [[ -z "$DOMAIN" || -z "$WORKTREE" ]]; then
  echo "Usage: $0 <domain> <worktree-path>" >&2
  echo "  Example: $0 todos ~/agentic-swarm-autoresearch-todos/" >&2
  exit 64
fi

case "$DOMAIN" in
  chat|swarm|todos|second-brain) ;;
  *)
    echo "ERROR: domain must be one of: chat, swarm, todos, second-brain (got: $DOMAIN)" >&2
    exit 64
    ;;
esac

if [[ ! -d "$WORKTREE" ]]; then
  echo "ERROR: worktree does not exist: $WORKTREE" >&2
  exit 66
fi

cd "$WORKTREE"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
EXPECTED_BRANCH="autoresearch/$DOMAIN"
if [[ "$BRANCH" != "$EXPECTED_BRANCH" ]]; then
  echo "WARNING: current branch is '$BRANCH', expected '$EXPECTED_BRANCH'" >&2
  echo "         Proceed only if you know what you're doing. Ctrl-C to abort." >&2
  sleep 3
fi

mkdir -p eval/fixtures research/loop-00 patches

created=()
exists=()

write_if_absent() {
  local path="$1"
  local content="$2"
  if [[ -e "$path" ]]; then
    exists+=("$path")
  else
    printf '%s' "$content" > "$path"
    created+=("$path")
  fi
}

# eval/ownership.json — MUST be edited by human before Loop 0 gate
write_if_absent "eval/ownership.json" "$(cat <<EOF
{
  "\$schema": "https://json-schema.org/draft/2020-12/schema",
  "domain": "$DOMAIN",
  "worktree": "$WORKTREE",
  "branch": "$EXPECTED_BRANCH",
  "baseline_tag": "TBD-after-loop-1-freeze",
  "owns": [
    "__EDIT_ME__: add file globs this domain owns, e.g. portal/src/app/$DOMAIN/**"
  ],
  "consumes_readonly": [
    "__EDIT_ME__: add globs this domain reads but must not modify"
  ],
  "forbidden": [
    "__EDIT_ME__: add globs that auto-reject candidates, e.g. other domains"
  ]
}
EOF
)"

# eval/models.json — pinned for frontier era; swap on OSS hosting
SWARM_DEFAULT_EXECUTOR="composer-2-fast"
if [[ "$DOMAIN" == "swarm" ]]; then
  SWARM_DEFAULT_EXECUTOR="claude-opus-4-7-thinking-high"
fi

write_if_absent "eval/models.json" "$(cat <<EOF
{
  "frozen_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "domain": "$DOMAIN",
  "hypothesis_generator": "claude-opus-4-7-thinking-high",
  "scorer":               "claude-opus-4-7-thinking-high",
  "merge_gate_reviewer":  "claude-opus-4-7-thinking-high",
  "executor_by_tag": {
    "mechanical": "composer-2-fast",
    "moderate":   "composer-2-fast",
    "deep":       "claude-opus-4-7-thinking-high"
  },
  "diversity_alternate_executor": "gpt-5.3-codex-high-fast",
  "swarm_default_executor":       "$SWARM_DEFAULT_EXECUTOR",
  "_note": "Re-freeze baseline whenever this file changes."
}
EOF
)"

# eval/scorecard.md — skeleton; floors MUST be filled in before Loop 1 gate
write_if_absent "eval/scorecard.md" "$(cat <<EOF
---
domain: $DOMAIN
floors:
  __EDIT_ME__: "set per-pillar SLA floors before Loop 1 freeze"
scoring_formula: |
  score = sum(pillar_improvement / null_hypothesis_variance for each pillar)
        - 10 * cross_domain_regressions
        - 100 * any_holdout_leak
        - 5  * scope_lock_violations
pass_threshold: 2.0
---

# Scorecard — $DOMAIN

## Pillars

(Populate after investigation in Loop 0.)

## SLA Floors

(Populate after baseline freeze in Loop 1.)

## Notes

- Null-hypothesis variance is re-measured every research loop; see research/loop-<N>/scorecard-null.json.
- pass_threshold gates winner advancement; below threshold => stagnant loop.
EOF
)"

# eval/harness.ts — skeleton; domain-specific fixtures + scoring live in eval/
write_if_absent "eval/harness.ts" "$(cat <<'EOF'
#!/usr/bin/env -S npx tsx
/**
 * vmc-autoresearch eval harness — skeleton
 *
 * Modes:
 *   baseline  : freeze per-pillar metrics at N runs -> eval/baseline.json
 *   score     : score a single candidate branch -> research/loop-<N>/scorecard-<candidate>.json
 *   holdout   : verifier-only; queries plx_autoresearch_verifier Postgres role
 *
 * Populate PILLARS + runFixture() before Loop 1 freeze.
 */

import { writeFileSync, readFileSync } from "node:fs";
import { parseArgs } from "node:util";

type Mode = "baseline" | "score" | "holdout";

interface PillarMetric {
  p50: number;
  p95: number;
  p99: number;
}

// TODO: populate from eval/scorecard.md pillars
const PILLARS = [
  // e.g. "crud_success_rate", "sharepoint_sync_ms"
] as const;

async function runFixture(fixture: unknown): Promise<Record<string, number>> {
  // TODO: implement per-domain fixture execution.
  // Must return one numeric value per pillar in PILLARS.
  throw new Error("runFixture not implemented — populate per domain in eval/harness.ts");
}

function percentile(xs: number[], p: number): number {
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.floor(sorted.length * p);
  return sorted[Math.min(idx, sorted.length - 1)];
}

async function main() {
  const { values } = parseArgs({
    options: {
      mode:      { type: "string" },
      out:       { type: "string" },
      n:         { type: "string", default: "300" },
      candidate: { type: "string" },
    },
  });

  const mode = values.mode as Mode | undefined;
  if (!mode || !values.out) {
    console.error("Usage: harness.ts --mode=<baseline|score|holdout> --out=<path> [--n=300] [--candidate=<name>]");
    process.exit(64);
  }

  if (mode === "holdout" && process.env.PGUSER !== "plx_autoresearch_verifier") {
    console.error("holdout mode requires PGUSER=plx_autoresearch_verifier");
    process.exit(77);
  }

  const n = Number(values.n);
  const samples: Record<string, number[]> = Object.fromEntries(PILLARS.map(p => [p, []]));

  for (let i = 0; i < n; i++) {
    const fixture = { id: i }; // TODO: load real fixtures from eval/fixtures/ or Postgres
    const result = await runFixture(fixture);
    for (const pillar of PILLARS) {
      samples[pillar].push(result[pillar]);
    }
  }

  const metrics: Record<string, PillarMetric> = {};
  for (const pillar of PILLARS) {
    const xs = samples[pillar];
    metrics[pillar] = { p50: percentile(xs, 0.5), p95: percentile(xs, 0.95), p99: percentile(xs, 0.99) };
  }

  const output = {
    frozen_at: new Date().toISOString(),
    mode,
    candidate: values.candidate ?? null,
    n_runs: n,
    pillars: metrics,
  };

  writeFileSync(values.out, JSON.stringify(output, null, 2));
  console.log(`wrote ${values.out}`);
}

main().catch(err => { console.error(err); process.exit(1); });
EOF
)"

# research/loop-00/investigation.md placeholder
write_if_absent "research/loop-00/investigation.md" "$(cat <<EOF
# Loop 0 Investigation — $DOMAIN

Populated by the explore subagent per SKILL.md Example A step 3.

## Component Map

(TBD)

## I/O Contracts

(TBD)

## Known Bug Reports

(TBD — from git log --grep and GitHub issues)

## Observed Reliability Weak Points

(TBD)

## Proposed Pillars

(TBD — these become keys in eval/baseline.json and eval/scorecard.md)
EOF
)"

# .gitignore for fixtures (optional; keep or remove based on size)
write_if_absent "eval/.gitignore" "$(cat <<'EOF'
# Keep fixtures tracked by default; uncomment if they become too large:
# fixtures/
EOF
)"

echo ""
echo "=== init-eval.sh complete ==="
echo "Domain:   $DOMAIN"
echo "Worktree: $WORKTREE"
echo "Branch:   $BRANCH"
echo ""
if (( ${#created[@]} > 0 )); then
  echo "Created (${#created[@]}):"
  printf '  %s\n' "${created[@]}"
fi
if (( ${#exists[@]} > 0 )); then
  echo "Already existed (${#exists[@]}; not overwritten):"
  printf '  %s\n' "${exists[@]}"
fi
echo ""
echo "Next steps:"
echo "  1) Edit eval/ownership.json — replace __EDIT_ME__ globs with real paths."
echo "  2) Edit eval/scorecard.md — define pillars + SLA floors."
echo "  3) Populate eval/harness.ts — implement PILLARS and runFixture()."
echo "  4) Run Loop 0 investigation (see SKILL.md Example A)."
echo "  5) Commit: git add eval/ research/loop-00/ && git commit -m 'feat(autoresearch-$DOMAIN): loop 0 scaffold'"
