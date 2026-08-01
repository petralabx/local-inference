#!/usr/bin/env bash
# parallel-multiagent-orchestrator — mock loop (skill regression)
#
# Proves Phase 3 exit criteria:
#   1) Skill loads via trigger phrase (file presence + frontmatter probe)
#   2) Mock loop with N=2 parallel best-of-n-runner candidates completes and
#      produces a scorecard
#   3) Scope-lock rejects an out-of-scope patch
#
# Self-contained: no network, no VMC MCP, no real subagent spawn. Synthesizes
# two candidate diffs, runs scope-lock + pick-winner locally, and asserts.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCOPE_LOCK="$SKILL_DIR/scripts/scope-lock.sh"
PICK_WINNER="$SKILL_DIR/scripts/pick-winner.sh"
SKILL_MD="$SKILL_DIR/SKILL.md"

WORKDIR="$(mktemp -d -t parallel-orch-mock-XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "[mock-loop] workdir: $WORKDIR"

# ----- 1) Exit-criterion: skill loads -----
if [[ ! -f "$SKILL_MD" ]]; then
  echo "FAIL: SKILL.md missing at $SKILL_MD" >&2
  exit 1
fi
if ! grep -qE '^name: parallel-multiagent-orchestrator$' "$SKILL_MD"; then
  echo "FAIL: SKILL.md frontmatter name mismatch" >&2
  exit 1
fi
if ! grep -qE '^description: Orchestrates N parallel hypothesis candidates' "$SKILL_MD"; then
  echo "FAIL: SKILL.md frontmatter description mismatch" >&2
  exit 1
fi
echo "[mock-loop] skill loads: OK (frontmatter matches)"

# ----- 2) Synthesize a mock domain workspace -----
cd "$WORKDIR"
mkdir -p eval research/loop-99/patches

cat > eval/ownership.json <<'JSON'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "domain": "todos",
  "worktree": "/tmp/parallel-orch-mock",
  "branch": "autoresearch/todos",
  "owns": [
    "domain/*",
    "eval/*",
    "research/**"
  ],
  "consumes_readonly": [
    "shared/readonly/*"
  ],
  "forbidden": [
    "other-domain/*",
    "master-only/*"
  ]
}
JSON

mkdir -p domain other-domain shared/readonly
echo "baseline content" > domain/owns_me.txt
echo "baseline content" > other-domain/forbidden_me.txt

# ----- 3) Synthesize 2 candidate patches -----
# Candidate hyp-01: in-scope (modifies domain/owns_me.txt)
cat > research/loop-99/patches/hyp-01.patch <<'DIFF'
diff --git a/domain/owns_me.txt b/domain/owns_me.txt
--- a/domain/owns_me.txt
+++ b/domain/owns_me.txt
@@ -1 +1 @@
-baseline content
+improved content from hyp-01
DIFF

# Candidate hyp-02: out-of-scope (modifies other-domain/forbidden_me.txt)
cat > research/loop-99/patches/hyp-02.patch <<'DIFF'
diff --git a/other-domain/forbidden_me.txt b/other-domain/forbidden_me.txt
--- a/other-domain/forbidden_me.txt
+++ b/other-domain/forbidden_me.txt
@@ -1 +1 @@
-baseline content
+sneaky cross-domain edit from hyp-02
DIFF

echo "[mock-loop] hyp-01 patch: in-scope (touches domain/owns_me.txt)"
echo "[mock-loop] hyp-02 patch: out-of-scope (touches other-domain/forbidden_me.txt)"

# ----- 4) Scope-lock each candidate -----
echo "[mock-loop] scope-lock hyp-01..."
if bash "$SCOPE_LOCK" todos research/loop-99/patches/hyp-01.patch eval/ownership.json; then
  HYP01_SCOPE="pass"
else
  echo "FAIL: hyp-01 should have passed scope-lock but exited $?" >&2
  exit 1
fi
echo "[mock-loop] scope-lock hyp-01 ... OK"

echo "[mock-loop] scope-lock hyp-02..."
set +e
bash "$SCOPE_LOCK" todos research/loop-99/patches/hyp-02.patch eval/ownership.json
HYP02_EXIT=$?
set -e
if [[ "$HYP02_EXIT" -ne 2 ]]; then
  echo "FAIL: hyp-02 should have exited 2 (forbidden) but exited $HYP02_EXIT" >&2
  exit 1
fi
echo "[mock-loop] scope-lock hyp-02 ... REJECTED (exit=$HYP02_EXIT, reason=forbidden)"

# ----- 5) Emit scorecards + null-arm -----
# hyp-01: eligible, wins with +3.5 combined pillar improvement
cat > research/loop-99/scorecard-hyp-01.json <<'JSON'
{
  "candidate": "hyp-01",
  "tag": "mechanical",
  "executor": "composer-2-fast",
  "status": "eligible",
  "pillar_improvements": {
    "crud_success_rate":  1.5,
    "schema_valid_response": 2.0
  },
  "penalties": {
    "cross_domain_regressions": 0,
    "holdout_leak": false,
    "scope_lock_violations": 0
  }
}
JSON

# hyp-02: rejected-scope (not eligible for scoring)
cat > research/loop-99/scorecard-hyp-02.json <<'JSON'
{
  "candidate": "hyp-02",
  "tag": "deep",
  "executor": "claude-opus-4-7-thinking-high",
  "status": "rejected-scope",
  "pillar_improvements": {},
  "penalties": {
    "cross_domain_regressions": 0,
    "holdout_leak": false,
    "scope_lock_violations": 1
  }
}
JSON

# Null-arm scorecard (unchanged baseline re-run)
cat > research/loop-99/scorecard-null.json <<'JSON'
{
  "candidate": "null",
  "status": "control",
  "null_variance": 0.08
}
JSON

# Baseline stub
cat > eval/baseline.json <<'JSON'
{
  "frozen_at": "2026-04-23T18:00:00Z",
  "domain": "todos",
  "pillars": {
    "crud_success_rate":      { "p50": 0.99, "p95": 0.98, "p99": 0.97 },
    "schema_valid_response":  { "p50": 1.00, "p95": 1.00, "p99": 0.99 }
  },
  "null_hypothesis_variance": {
    "crud_success_rate":     0.003,
    "schema_valid_response": 0.001
  }
}
JSON

echo "[mock-loop] scorecards written: hyp-01, hyp-02, null"

# ----- 6) Pick winner -----
bash "$PICK_WINNER" \
  --loop=99 \
  --domain=todos \
  --scorecards="research/loop-99/scorecard-hyp-*.json" \
  --null=research/loop-99/scorecard-null.json \
  --baseline=eval/baseline.json \
  --out=research/loop-99/REPORT.md \
  --pass-threshold=2.0

# ----- 7) Assert REPORT.md says winner=hyp-01 and records hyp-02 rejection -----
REPORT="research/loop-99/REPORT.md"

if ! grep -qE '^winner: hyp-01$' "$REPORT"; then
  echo "FAIL: REPORT.md did not declare hyp-01 as winner" >&2
  cat "$REPORT" >&2
  exit 1
fi
if ! grep -qE '\| hyp-02 \|.*\| rejected-scope \|' "$REPORT"; then
  echo "FAIL: REPORT.md did not record hyp-02 as rejected-scope" >&2
  cat "$REPORT" >&2
  exit 1
fi

echo "[mock-loop] REPORT.md written: $WORKDIR/$REPORT"
echo ""
echo "[mock-loop] EXIT CRITERIA MET:"
echo "  ✓ 2 parallel candidates processed"
echo "  ✓ scope-lock rejected 1 out-of-scope candidate (hyp-02, exit=2)"
echo "  ✓ scorecard produced (hyp-01, hyp-02, null)"
echo "  ✓ REPORT.md declares winner=hyp-01 with rubric evidence"
echo ""
exit 0
