#!/usr/bin/env bash
#
# discovery-validate.sh — validate a guided-project-discovery DISCOVERY.md ledger.
#
# Usage:
#   discovery-validate.sh <path/to/DISCOVERY.md>
#   discovery-validate.sh --selftest
#
# Checks frontmatter, required sections, lens-table well-formedness, and the two
# invariants that make a run resumable: lens_cursor names a real lens, and every
# answered lens has an answer block.
#
# Exit 0 when valid, 1 when invalid.

set -uo pipefail

usage() {
  echo "usage: discovery-validate.sh <path/to/DISCOVERY.md> | --selftest" >&2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then :; else REPO_ROOT="$(pwd)"; fi

arg="${1:-}"
if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
  usage
  exit 0
fi

# Resolve the sample relative to this script so the selftest works both in the
# skills repo and in a consuming repo that installed under .cursor/skills/.
if [[ "$arg" == "--selftest" ]]; then
  exec "$0" "${SCRIPT_DIR}/../examples/DISCOVERY.sample.md"
fi

if [[ -z "$arg" ]]; then
  usage
  exit 1
fi

if [[ "$arg" = /* ]]; then
  ledger="$arg"
else
  ledger="${REPO_ROOT}/${arg}"
  [[ -f "$ledger" ]] || ledger="$arg"
fi

if [[ ! -f "$ledger" ]]; then
  echo "FAIL: file not found: $arg" >&2
  usage
  exit 1
fi

awk '
function trim(s){ gsub(/^[[:space:]]+|[[:space:]]+$/,"",s); return s }
function fail(msg){ print "FAIL: " msg; errs++ }

BEGIN {
  errs=0; fm_seen=0; in_fm=0; section=""; lens_count=0; answer_count=0
  split("interviewing ready-for-review in-review approved handed-off", st, " ")
  for (i in st) valid_status[st[i]]=1
  split("research research+plan research+plan+execute", md, " ")
  for (i in md) valid_mode[md[i]]=1
  split("open asked answered prefilled waived", ls, " ")
  for (i in ls) valid_lens_status[ls[i]]=1
}

/^---[[:space:]]*$/ {
  fm_seen++
  if (fm_seen == 1) { in_fm=1; next }
  if (fm_seen == 2) { in_fm=0; next }
}

in_fm == 1 {
  if (match($0, /^slug:[[:space:]]*/))        { slug=trim(substr($0, RLENGTH+1)) }
  if (match($0, /^created:[[:space:]]*/))     { created=trim(substr($0, RLENGTH+1)) }
  if (match($0, /^updated:[[:space:]]*/))     { updated=trim(substr($0, RLENGTH+1)) }
  if (match($0, /^status:[[:space:]]*/))      { status=trim(substr($0, RLENGTH+1)) }
  if (match($0, /^mode:[[:space:]]*/))        { mode=trim(substr($0, RLENGTH+1)) }
  if (match($0, /^lens_cursor:[[:space:]]*/)) { cursor=trim(substr($0, RLENGTH+1)) }
  next
}

/^## Mission[[:space:]]*$/      { sec_mission=1;   section="mission";   next }
/^## Lenses[[:space:]]*$/       { sec_lenses=1;    section="lenses";    next }
/^## Answers[[:space:]]*$/      { sec_answers=1;   section="answers";   next }
/^## Assumptions[[:space:]]*$/  { sec_assump=1;    section="assump";    next }
/^## Non-Goals[[:space:]]*$/    { sec_nongoals=1;  section="nongoals";  next }
/^## Evidence[[:space:]]*$/     { sec_evidence=1;  section="evidence";  next }
/^## Decision Log[[:space:]]*$/ { sec_decisions=1; section="decisions"; next }
/^## Handoff[[:space:]]*$/      { sec_handoff=1;   section="handoff";   next }
/^## /                          { section="other"; next }

section == "lenses" && /^\|/ {
  n=split($0, f, "|")
  if (n < 6) { fail("lens table row has fewer than 5 columns: " trim($0)); next }
  id=trim(f[2])
  if (id == "Lens" || id == "" || id ~ /^-+$/) next
  if (id !~ /^L[0-9]+$/) { fail("lens id " id " is not of the form L<n>"); next }
  if (id in seen_lens) { fail("duplicate lens id " id) }
  seen_lens[id]=1
  lens_count++
  order[lens_count]=id
  blocking[id]=trim(f[4])
  lstatus[id]=trim(f[5])
  answered_at[id]=trim(f[6])
  if (!(lstatus[id] in valid_lens_status)) fail("lens " id " has unknown status " lstatus[id])
  if (blocking[id] != "yes" && blocking[id] != "no") fail("lens " id " blocking column must be yes or no, got " blocking[id])
  next
}

section == "answers" && /^### / {
  aid=trim(substr($0, 5))
  sub(/[[:space:]].*$/, "", aid)
  has_answer[aid]=1
  answer_count++
  next
}

section == "mission" { if (trim($0) != "") mission_lines++ }
section == "handoff" { if (trim($0) != "") handoff_lines++ }

END {
  if (fm_seen < 2) fail("missing or incomplete frontmatter block")
  if (slug == "")    fail("frontmatter missing slug")
  if (created == "") fail("frontmatter missing created")
  if (updated == "") fail("frontmatter missing updated")
  if (cursor == "")  fail("frontmatter missing lens_cursor")
  if (status == "")  fail("frontmatter missing status")
  else if (!(status in valid_status)) fail("frontmatter status " status " is not a known status")
  if (mode == "")    fail("frontmatter missing mode")
  else if (!(mode in valid_mode)) fail("frontmatter mode " mode " is not one of research, research+plan, research+plan+execute")

  if (!sec_mission)   fail("missing section: ## Mission")
  if (!sec_lenses)    fail("missing section: ## Lenses")
  if (!sec_answers)   fail("missing section: ## Answers")
  if (!sec_assump)    fail("missing section: ## Assumptions")
  if (!sec_nongoals)  fail("missing section: ## Non-Goals")
  if (!sec_evidence)  fail("missing section: ## Evidence")
  if (!sec_decisions) fail("missing section: ## Decision Log")
  if (!sec_handoff)   fail("missing section: ## Handoff")

  if (mission_lines < 1) fail("## Mission is empty")
  if (handoff_lines < 1) fail("## Handoff is empty")

  if (lens_count < 1) {
    fail("## Lenses table has no lens rows")
  } else {
    # Resumability: the cursor must name a lens that exists.
    if (cursor != "" && cursor != "done" && !(cursor in seen_lens))
      fail("lens_cursor " cursor " does not appear in the ## Lenses table")

    for (i=1; i<=lens_count; i++) {
      id=order[i]
      if (lstatus[id] == "answered" || lstatus[id] == "prefilled") {
        # An em dash or hyphen placeholder carries no digits; a timestamp does.
        if (answered_at[id] !~ /[0-9]/)
          fail("lens " id " is " lstatus[id] " but has no Answered timestamp")
        if (!(id in has_answer))
          fail("lens " id " is " lstatus[id] " but has no ### " id " block in ## Answers")
      }
      # A ledger offered for review must not still be waiting on a blocking lens.
      if (status != "interviewing" && blocking[id] == "yes" && (lstatus[id] == "open" || lstatus[id] == "asked"))
        fail("status is " status " but blocking lens " id " is still " lstatus[id])
    }
  }

  if (errs == 0) {
    printf "OK: DISCOVERY.md valid (%d lenses, %d answers, mode %s, status %s)\n", lens_count, answer_count, mode, status
    exit 0
  }
  exit 1
}
' "$ledger"
