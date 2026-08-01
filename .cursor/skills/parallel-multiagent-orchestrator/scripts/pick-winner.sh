#!/usr/bin/env bash
# parallel-multiagent-orchestrator — winner picker (mock-friendly)
#
# Usage: pick-winner.sh --loop=<N> --domain=<d> \
#                       --scorecards=<glob> \
#                       --null=<path> \
#                       --baseline=<path> \
#                       --out=<REPORT.md path> \
#                       [--pass-threshold=2.0]
#
# Reads candidate scorecards + null-arm scorecard, computes loop_score per
# candidate, picks the max that passes the threshold, and writes REPORT.md.
#
# Scorecard JSON format (minimum):
#   {
#     "candidate": "hyp-01",
#     "tag": "mechanical",
#     "executor": "composer-2-fast",
#     "status": "eligible" | "rejected-scope" | "rejected-tier1" | "blocker",
#     "pillar_improvements": { "pillar_name": <value-in-variance-units>, ... },
#     "penalties": {
#       "cross_domain_regressions": 0,
#       "holdout_leak": false,
#       "scope_lock_violations": 0
#     }
#   }
#
# loop_score = sum(pillar_improvements) - 10*regressions - 100*holdout_leak - 5*scope_violations

set -euo pipefail

LOOP=""
DOMAIN=""
SCORECARDS_GLOB=""
NULL_PATH=""
BASELINE_PATH=""
OUT=""
THRESHOLD="2.0"

for arg in "$@"; do
  case "$arg" in
    --loop=*)           LOOP="${arg#*=}" ;;
    --domain=*)         DOMAIN="${arg#*=}" ;;
    --scorecards=*)     SCORECARDS_GLOB="${arg#*=}" ;;
    --null=*)           NULL_PATH="${arg#*=}" ;;
    --baseline=*)       BASELINE_PATH="${arg#*=}" ;;
    --out=*)            OUT="${arg#*=}" ;;
    --pass-threshold=*) THRESHOLD="${arg#*=}" ;;
    *) echo "Unknown arg: $arg" >&2; exit 64 ;;
  esac
done

for v in LOOP DOMAIN SCORECARDS_GLOB NULL_PATH BASELINE_PATH OUT; do
  if [[ -z "${!v}" ]]; then
    flag=$(echo "$v" | tr '[:upper:]_' '[:lower:]-')
    echo "ERROR: missing --${flag}" >&2
    echo "Usage: see header of $0" >&2
    exit 64
  fi
done

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required" >&2
  exit 64
fi

shopt -s nullglob
CARDS=( $SCORECARDS_GLOB )
if (( ${#CARDS[@]} == 0 )); then
  echo "ERROR: no scorecards matched: $SCORECARDS_GLOB" >&2
  exit 65
fi

# Per-candidate loop_score
declare -a ROWS
WINNER=""
WINNER_SCORE="-99999"

for card in "${CARDS[@]}"; do
  candidate=$(jq -r '.candidate // "unknown"' "$card")
  tag=$(jq -r '.tag // "unknown"' "$card")
  executor=$(jq -r '.executor // "unknown"' "$card")
  status=$(jq -r '.status // "eligible"' "$card")

  branch=$(jq -r '.branch // empty' "$card" 2>/dev/null || true)
  if [[ -z "$branch" ]]; then
    branch="autoresearch/${DOMAIN}/loop-${LOOP}/${candidate}"
  fi

  if [[ "$status" != "eligible" ]]; then
    ROWS+=("| $candidate | $tag | $executor | $branch | $status | n/a |")
    continue
  fi

  # Sum pillar improvements and apply penalties.
  score=$(jq -r '
    (.pillar_improvements // {} | [to_entries[].value] | add // 0)
    - (10  * (.penalties.cross_domain_regressions // 0))
    - (100 * (if (.penalties.holdout_leak // false) then 1 else 0 end))
    - (5   * (.penalties.scope_lock_violations // 0))
  ' "$card")

  ROWS+=("| $candidate | $tag | $executor | $branch | eligible | $score |")

  # Track max
  if awk -v a="$score" -v b="$WINNER_SCORE" 'BEGIN{exit !(a>b)}'; then
    WINNER="$candidate"
    WINNER_SCORE="$score"
  fi
done

# Apply threshold gate
STAGNANT="false"
if awk -v a="$WINNER_SCORE" -v t="$THRESHOLD" 'BEGIN{exit !(a>=t)}'; then
  :
else
  STAGNANT="true"
  WINNER="none"
fi

NULL_VARIANCE=$(jq -r '.null_variance // 0' "$NULL_PATH" 2>/dev/null || echo 0)

mkdir -p "$(dirname "$OUT")"

cat > "$OUT" <<EOF
---
domain: $DOMAIN
loop: $LOOP
generated_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
orchestrator_version: parallel-multiagent-orchestrator@1.0.0
parent_todo_id: ar-$DOMAIN-l$LOOP
winner: $WINNER
loop_score: $WINNER_SCORE
pass_threshold: $THRESHOLD
stagnant: $STAGNANT
auto_escalations: 0
---

# Loop $LOOP Report — $DOMAIN

## Candidates

| Hyp | Tag | Executor | Branch | Status | loop_score |
|---|---|---|---|---|---|
$(printf '%s\n' "${ROWS[@]}")

## Null-Hypothesis Control Arm

- Re-run baseline variance: $NULL_VARIANCE
- Threshold for "improvement": > 1.0 variance units

## Winner Selection

$(if [[ "$STAGNANT" == "true" ]]; then
  echo "No winner declared. Max loop_score ($WINNER_SCORE) below pass_threshold ($THRESHOLD)."
  echo "Loop marked stagnant; next loop inherits these hypotheses or re-generates."
else
  echo "Winner: **$WINNER** with loop_score=$WINNER_SCORE (pass_threshold=$THRESHOLD)."
fi)

## Scorecards Consumed

$(for card in "${CARDS[@]}"; do echo "- $card"; done)

## Baseline Reference

- $BASELINE_PATH

## Next Loop Seeds

(Populate after human review.)
EOF

echo "[pick-winner] winner=$WINNER loop_score=$WINNER_SCORE stagnant=$STAGNANT"
echo "[pick-winner] wrote $OUT"
