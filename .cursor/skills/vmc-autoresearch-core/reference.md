# VMC AutoResearch Core — Reference

Full schemas, gate commands, and scoring math. Load this on demand from [SKILL.md](SKILL.md).

## 1. VMC MCP Tool Schemas (verbatim)

Schemas live at `~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/`. Read each descriptor before invoking the tool.

### vmc_get_context

```json
{
  "name": "vmc_get_context",
  "description": "Get current VMC context: projects, todos, blocked items, system health. Use depth=compact (default, ~200 tokens) for quick reads, depth=full (~600 tokens) for architectural decisions.",
  "arguments": {
    "type": "object",
    "properties": {
      "depth": { "type": "string", "enum": ["compact", "full"], "default": "compact" },
      "project": { "type": "string" }
    }
  }
}
```

### vmc_get_roadmap

```json
{
  "name": "vmc_get_roadmap",
  "description": "Get prioritized work queue — what should be worked on next. Optionally filter by project.",
  "arguments": {
    "type": "object",
    "properties": { "project": { "type": "string" } }
  }
}
```

### vmc_checkout_task

```json
{
  "name": "vmc_checkout_task",
  "description": "Claim a todo before starting work. Sets status to 'progress' and assigns to Cursor. Returns 409 if already assigned to another agent.",
  "arguments": {
    "type": "object",
    "properties": { "todoId": { "type": "string" } },
    "required": ["todoId"]
  }
}
```

### vmc_report_progress

```json
{
  "name": "vmc_report_progress",
  "description": "Report progress on a checked-out todo. Call after completing subtasks or roughly every 10-15 minutes.",
  "arguments": {
    "type": "object",
    "properties": {
      "todoId":      { "type": "string" },
      "progressPct": { "type": "number", "minimum": 0, "maximum": 100 },
      "evidence":    { "type": "string" },
      "phase":       { "type": "string" },
      "notes":       { "type": "string" }
    },
    "required": ["todoId"]
  }
}
```

### vmc_complete_task

```json
{
  "name": "vmc_complete_task",
  "description": "Mark a todo as complete with evidence. Moves to QA review. Include commit SHA and PR URL when applicable.",
  "arguments": {
    "type": "object",
    "properties": {
      "todoId":       { "type": "string" },
      "evidence":     { "type": "string" },
      "commitSha":    { "type": "string" },
      "prUrl":        { "type": "string" },
      "filesChanged": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["todoId", "evidence"]
  }
}
```

### vmc_get_repo_health / vmc_get_dependency_risks / vmc_get_unused_candidates

No arguments (except optional `tool` filter on `get_unused_candidates`). Called before Loop 5 merge gate. Refresh cache first via `scripts/code-health-scan.sh`.

## 2. eval/ Directory Schemas

### eval/ownership.json

Canonical scope-lock manifest. Pre-commit hook rejects any candidate patch touching files not in `owns` or consuming files outside `consumes_readonly`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "domain": "todos",
  "worktree": "~/agentic-swarm-autoresearch-todos/",
  "branch": "autoresearch/todos",
  "baseline_tag": "autoresearch/todos-baseline-2026-04-23T17:00Z",
  "owns": [
    "portal/src/app/todos/**",
    "portal/src/lib/todos/**",
    "apps/vmc-web/src/lib/todos/**",
    "apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts"
  ],
  "consumes_readonly": [
    "portal/src/lib/auth/**",
    "prisma/schema.prisma",
    "apps/vmc-web/src/lib/vmc/core/**"
  ],
  "forbidden": [
    "portal/src/app/(chat|second-brain|admin)/**",
    "portal/src/lib/chat/**",
    "portal/src/lib/second-brain/**",
    "master-only/**"
  ]
}
```

### eval/models.json

Pinned model IDs per tier. Baseline must be re-frozen if this file changes.

```json
{
  "frozen_at": "2026-04-23T17:00:00Z",
  "hypothesis_generator": "claude-opus-4-7-thinking-high",
  "scorer":               "claude-opus-4-7-thinking-high",
  "merge_gate_reviewer":  "claude-opus-4-7-thinking-high",
  "executor_by_tag": {
    "mechanical": "composer-2-fast",
    "moderate":   "composer-2-fast",
    "deep":       "claude-opus-4-7-thinking-high"
  },
  "diversity_alternate_executor": "gpt-5.3-codex-high-fast",
  "swarm_default_executor":       "claude-opus-4-7-thinking-high"
}
```

### eval/baseline.json

Frozen at Loop 1. Per-pillar percentiles. Must include raw N and fixture hash.

```json
{
  "frozen_at": "2026-04-23T18:00:00Z",
  "domain": "todos",
  "models": { "$ref": "models.json" },
  "fixture_set_hash": "sha256:3f9a...c021",
  "n_runs": 300,
  "pillars": {
    "crud_success_rate":       { "p50": 0.992, "p95": 0.983, "p99": 0.971 },
    "sharepoint_sync_ms":      { "p50": 420,   "p95": 1180,  "p99": 2340 },
    "roadmap_parity_pct":      { "p50": 0.998, "p95": 0.990, "p99": 0.982 },
    "schema_valid_response":   { "p50": 1.000, "p95": 1.000, "p99": 0.998 }
  },
  "null_hypothesis_variance": {
    "crud_success_rate":     0.003,
    "sharepoint_sync_ms":    45,
    "roadmap_parity_pct":    0.002,
    "schema_valid_response": 0.001
  }
}
```

### eval/scorecard.md

Per-pillar SLA floors + scoring formula. Machine-parseable front-matter + human narrative.

```yaml
---
domain: todos
floors:
  crud_success_rate: ">= 0.995"
  sharepoint_sync_p95_ms: "<= 1000"
  roadmap_parity_pct: ">= 0.999"
  schema_valid_response: "== 1.000"
scoring_formula: |
  score = sum(pillar_improvement / null_hypothesis_variance for each pillar)
        - 10 * cross_domain_regressions
        - 100 * any_holdout_leak
pass_threshold: 2.0
---
```

### eval/holdout.ref.json

Hash reference to Postgres holdout rows. The actual payloads live in the DB.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "domain": "todos",
  "db_table": "autoresearch_holdout",
  "row_hashes": [
    "sha256:a3d9...8e10",
    "sha256:b4e1...3f22"
  ],
  "verified_at": "2026-04-23T18:00:00Z",
  "verifier_role": "plx_autoresearch_verifier"
}
```

## 3. Postgres Schema (holdout + replay corpus)

Migration lives in `prisma/migrations/<timestamp>_autoresearch_platform/migration.sql`.

```sql
CREATE TABLE autoresearch_holdout (
  fixture_hash TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  loop_id INT NOT NULL,
  fixture_payload JSONB NOT NULL,
  frozen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  scored_by_verifier_at TIMESTAMPTZ,
  seen_by_agent_at TIMESTAMPTZ  -- TRIPWIRE: if set, merge gate blocks
);

CREATE TABLE autoresearch_replay_corpus (
  trajectory_hash TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  domain TEXT,
  outcome TEXT CHECK (outcome IN ('success', 'partial', 'failure')),
  trajectory JSONB NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE ROLE plx_autoresearch_agent NOLOGIN;
CREATE ROLE plx_autoresearch_verifier NOLOGIN;

REVOKE ALL ON autoresearch_holdout FROM PUBLIC;
REVOKE ALL ON autoresearch_holdout FROM plx_autoresearch_agent;
GRANT SELECT, UPDATE ON autoresearch_holdout TO plx_autoresearch_verifier;
GRANT SELECT ON autoresearch_replay_corpus TO plx_autoresearch_agent;
GRANT SELECT ON autoresearch_replay_corpus TO plx_autoresearch_verifier;

-- Tripwire trigger: if anyone updates seen_by_agent_at, flag it
CREATE OR REPLACE FUNCTION autoresearch_holdout_tripwire()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.seen_by_agent_at IS NOT NULL AND OLD.seen_by_agent_at IS NULL THEN
    PERFORM pg_notify('autoresearch_holdout_leak', NEW.fixture_hash);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER autoresearch_holdout_tripwire_trigger
  BEFORE UPDATE ON autoresearch_holdout
  FOR EACH ROW EXECUTE FUNCTION autoresearch_holdout_tripwire();
```

## 4. Loop Gate Commands (exact)

Run these at each loop boundary. Paste output verbatim into `research/loop-<N>/REPORT.md`.

### Loop 0 gate

```bash
# Validate ownership manifest syntax + no out-of-scope file references
jq '.' eval/ownership.json >/dev/null
rg -l -f <(jq -r '.forbidden[]' eval/ownership.json) research/loop-00/investigation.md && exit 1 || exit 0
```

### Loop 1 gate (baseline freeze)

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
npx tsx eval/harness.ts --mode=baseline --out=eval/baseline.json --n=300
psql "$DATABASE_URL" -c "SELECT count(*) FROM autoresearch_holdout WHERE domain='<domain>';"
sha256sum eval/baseline.json
```

### Loops 2-4 gate (research runs)

```bash
# Per candidate:
npm test -- <domain>-contracts
npx tsx eval/harness.ts --mode=score --candidate=<hyp-M> --out=research/loop-<N>/scorecard-<hyp-M>.json
# Null-hypothesis control arm:
npx tsx eval/harness.ts --mode=score --candidate=baseline --out=research/loop-<N>/scorecard-null.json

# Cross-domain regression check:
for d in chat todos second-brain swarm; do
  [ "$d" = "<domain>" ] && continue
  npm test -- $d-contracts || exit 1
done

# Scope-lock check:
.cursor/hooks/scope-lock.sh <domain> research/loop-<N>/hyp-<M>.patch
```

### Loop 5 gate (implementation + merge)

```bash
# Full verification matrix:
bash scripts/validate.sh
npm test -- .*-contracts  # all domain contract suites
npm test -- cross-domain

# Verifier scores holdout (uses plx_autoresearch_verifier DB role):
PGUSER=plx_autoresearch_verifier npx tsx eval/harness.ts --mode=holdout --out=research/loop-05/holdout-scorecard.json

# Holdout tripwire check:
psql "$DATABASE_URL" -c "SELECT count(*) FROM autoresearch_holdout WHERE seen_by_agent_at IS NOT NULL;"
# Must return 0.
```

## 5. Scoring Math

Per-pillar improvement is measured in **null-hypothesis-variance units** (similar to z-score) so cross-pillar summation is meaningful:

```
pillar_improvement = (candidate_metric - baseline_metric) / null_hypothesis_variance
```

Aggregate loop score:

```
loop_score = sum(pillar_improvement for each pillar)
           - 10 * count(cross_domain_regressions)
           - 100 * any_holdout_leak
           - 5  * count(scope_lock_violations)
```

Winner is max `loop_score` that also passes Tier-1 + cross-domain contract suites. `pass_threshold` (per scorecard) gates whether the winner advances at all; below threshold => stagnant loop.

## 6. Null-Hypothesis Control Arm

Every research loop re-runs the **unchanged baseline** under the same harness, models, fixtures, and timing as the candidates. Variance between the baseline's two runs (frozen at Loop 1 vs. re-run this loop) establishes the noise floor. A candidate that beats baseline by less than 1 variance unit is **not an improvement** — it's noise.

## 7. Ownership Manifest Enforcement

`.cursor/hooks/scope-lock.sh` is invoked per candidate patch:

```bash
#!/usr/bin/env bash
set -euo pipefail
DOMAIN=$1
PATCH=$2
MANIFEST="eval/ownership.json"
OWNS=$(jq -r '.owns[]' "$MANIFEST")
FORBIDDEN=$(jq -r '.forbidden[]' "$MANIFEST")

TOUCHED=$(git apply --stat "$PATCH" | awk '{print $1}')

for f in $TOUCHED; do
  for pattern in $FORBIDDEN; do
    [[ $f == $pattern ]] && { echo "SCOPE_LOCK_VIOLATION forbidden: $f"; exit 2; }
  done
  matched=false
  for pattern in $OWNS; do
    [[ $f == $pattern ]] && { matched=true; break; }
  done
  $matched || { echo "SCOPE_LOCK_VIOLATION not_owned: $f"; exit 3; }
done
exit 0
```

## 8. Stop-Condition Evidence Format

When a hard stop fires, write `research/loop-<N>/BLOCKER.md`:

```markdown
# BLOCKER — <domain> loop <N>

- **Condition fired:** <stop_if key>
- **Detected at:** <ISO timestamp>
- **Evidence:** <path to tool output / log excerpt / scorecard>
- **Recommended next action:** <one sentence>
- **Human required:** <true|false>
```

Then `vmc_report_progress` with `phase="blocked"` and link to this file in `evidence`.

## 9. Related Documents

- Parent plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](.cursor/plans/vmc-autoresearch-platform.plan.md)
- Verifier: [`.cursor/skills/autonomous-verifier/SKILL.md`](../autonomous-verifier/SKILL.md)
- Oneshot: [`.cursor/skills/vmc-autopilot-oneshot/SKILL.md`](../vmc-autopilot-oneshot/SKILL.md)
- Staging guard: `source ~/.secrets-env.staging && bash scripts/assert-staging-context.sh`
- Roadmap sync: [`.cursor/rules/vmc-roadmap-sharepoint-sync.mdc`](../../rules/vmc-roadmap-sharepoint-sync.mdc)
