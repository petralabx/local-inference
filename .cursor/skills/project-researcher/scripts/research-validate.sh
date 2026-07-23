#!/usr/bin/env bash
#
# research-validate.sh — validate a project-researcher RESEARCH.md brief.
#
# Usage:
#   research-validate.sh <path/to/RESEARCH.md>
#   research-validate.sh --selftest
#
# Exit 0 when valid, 1 when invalid.

set -uo pipefail

usage() {
  echo "usage: research-validate.sh <path/to/RESEARCH.md> | --selftest" >&2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then :; else REPO_ROOT="$(pwd)"; fi

arg="${1:-}"
if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$arg" == "--selftest" ]]; then
  sample_rel=".cursor/skills/project-researcher/examples/RESEARCH.sample.md"
  exec "$0" "$sample_rel"
fi

if [[ -z "$arg" ]]; then
  usage
  exit 1
fi

if [[ "$arg" = /* ]]; then
  brief="$arg"
else
  brief="${REPO_ROOT}/${arg}"
fi

if [[ ! -f "$brief" ]]; then
  echo "FAIL: file not found: $brief" >&2
  usage
  exit 1
fi

awk '
function trim(s){ gsub(/^[[:space:]]+|[[:space:]]+$/,"",s); return s }
function fail(msg){ print "FAIL: " msg; errs++ }

BEGIN {
  errs=0
  in_fm=0
  fm_seen=0
  in_candidate=0
  in_recommendation=0
  approach_idx=0
}

/^---[[:space:]]*$/ {
  fm_seen++
  if (fm_seen == 1) { in_fm=1; next }
  if (fm_seen == 2) { in_fm=0; next }
}

in_fm == 1 {
  if ($0 ~ /^slug:[[:space:]]*[^[:space:]].*$/) slug_ok=1
  if ($0 ~ /^created:[[:space:]]*[^[:space:]].*$/) created_ok=1
  if ($0 ~ /^status:[[:space:]]*[^[:space:]].*$/) status_ok=1
  if ($0 ~ /^rubric_score:[[:space:]]*[0-9]+([.][0-9]+)?[[:space:]]*$/) rubric_ok=1
  next
}

/^## Mission and Context[[:space:]]*$/ { sec_mission=1; in_candidate=0; in_recommendation=0; next }
/^## Internal Findings[[:space:]]*$/   { sec_internal=1; in_candidate=0; in_recommendation=0; next }
/^## External Findings[[:space:]]*$/   { sec_external=1; in_candidate=0; in_recommendation=0; next }
/^## Candidate Approaches[[:space:]]*$/ { sec_candidates=1; in_candidate=1; in_recommendation=0; next }
/^## Recommendation[[:space:]]*$/      { sec_recommendation=1; in_candidate=0; in_recommendation=1; next }
/^## Open Questions[[:space:]]*$/      { sec_open_questions=1; in_candidate=0; in_recommendation=0; next }
/^## Sources[[:space:]]*$/             { sec_sources=1; in_candidate=0; in_recommendation=0; next }

in_candidate == 1 && /^### Approach [0-9]+[[:space:]]*-/ {
  approach_idx++
  approach_count=approach_idx
  next
}

in_candidate == 1 && approach_idx > 0 && /^- Pros:[[:space:]]*.+$/         { has_pros[approach_idx]=1; next }
in_candidate == 1 && approach_idx > 0 && /^- Cons:[[:space:]]*.+$/         { has_cons[approach_idx]=1; next }
in_candidate == 1 && approach_idx > 0 && /^- Risk:[[:space:]]*.+$/         { has_risk[approach_idx]=1; next }
in_candidate == 1 && approach_idx > 0 && /^- Effort:[[:space:]]*.+$/       { has_effort[approach_idx]=1; next }
in_candidate == 1 && approach_idx > 0 && /^- Blast Radius:[[:space:]]*.+$/ { has_blast[approach_idx]=1; next }

in_recommendation == 1 && $0 !~ /^## / {
  line=trim($0)
  if (line != "") rec_lines++
}

sec_sources == 1 && /^- [^[:space:]].*$/ { source_lines++ }

END {
  if (fm_seen < 2) fail("missing or incomplete frontmatter block")
  if (!slug_ok) fail("frontmatter missing slug")
  if (!created_ok) fail("frontmatter missing created")
  if (!status_ok) fail("frontmatter missing status")
  if (!rubric_ok) fail("frontmatter missing numeric rubric_score")

  if (!sec_mission) fail("missing section: ## Mission and Context")
  if (!sec_internal) fail("missing section: ## Internal Findings")
  if (!sec_external) fail("missing section: ## External Findings")
  if (!sec_candidates) fail("missing section: ## Candidate Approaches")
  if (!sec_recommendation) fail("missing section: ## Recommendation")
  if (!sec_open_questions) fail("missing section: ## Open Questions")
  if (!sec_sources) fail("missing section: ## Sources")

  if (approach_count < 2) {
    fail("need at least 2 candidate approaches")
  } else {
    for (i=1; i<=approach_count; i++) {
      if (!has_pros[i])   fail("approach " i " missing - Pros:")
      if (!has_cons[i])   fail("approach " i " missing - Cons:")
      if (!has_risk[i])   fail("approach " i " missing - Risk:")
      if (!has_effort[i]) fail("approach " i " missing - Effort:")
      if (!has_blast[i])  fail("approach " i " missing - Blast Radius:")
    }
  }

  if (rec_lines < 1) fail("recommendation section is empty")
  if (source_lines < 1) fail("sources section needs at least one bullet")

  if (errs == 0) {
    print "OK: RESEARCH.md schema valid (" approach_count " approaches)"
    exit 0
  }
  exit 1
}
' "$brief"
