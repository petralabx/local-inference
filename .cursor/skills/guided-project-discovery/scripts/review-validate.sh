#!/usr/bin/env bash
#
# review-validate.sh — validate a collaborative review round.
#
# Usage:
#   review-validate.sh <path/to/round-<n>.md>
#   review-validate.sh --selftest
#   review-validate.sh --digest <path/to/CANDIDATE.md>
#
# Enforces the mechanical parts of review-gate.md that a human reading the round
# cannot reliably check by eye:
#
#   * every feedback item carries a channel, durable provenance, and the digest
#     of the candidate the reviewer actually saw
#   * every blocking item has a disposition decided by a named human
#   * every approval names the current candidate digest and current authority
#     revisions — a stale approval fails rather than being quietly counted
#   * no review round authorizes execution, whatever its approval count
#
# Exit 0 when valid, 1 when invalid.

set -uo pipefail

usage() {
  echo "usage: review-validate.sh <path/to/round-<n>.md> | --selftest | --digest <CANDIDATE.md>" >&2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then :; else REPO_ROOT="$(pwd)"; fi

arg="${1:-}"
if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$arg" == "--selftest" ]]; then
  exec "$0" "${SCRIPT_DIR}/../examples/REVIEW.sample.md"
fi

# A candidate is content-addressed: its directory name is its digest. If the
# recomputed digest differs, the candidate was mutated in place.
if [[ "$arg" == "--digest" ]]; then
  candidate="${2:-}"
  if [[ -z "$candidate" || ! -f "$candidate" ]]; then
    echo "FAIL: --digest needs a readable CANDIDATE.md path" >&2
    exit 1
  fi
  actual="sha256:$(sha256sum "$candidate" | cut -d' ' -f1)"
  claimed="$(basename "$(dirname "$candidate")")"
  echo "computed: $actual"
  if [[ "$claimed" == sha256:* || "$claimed" =~ ^[0-9a-f]{64}$ ]]; then
    [[ "$claimed" == sha256:* ]] || claimed="sha256:${claimed}"
    if [[ "$actual" != "$claimed" ]]; then
      echo "FAIL: candidate directory claims $claimed but content hashes to $actual" >&2
      exit 1
    fi
    echo "OK: candidate content matches its address"
  else
    echo "note: parent directory $claimed is not a digest — nothing to compare against"
  fi
  exit 0
fi

if [[ -z "$arg" ]]; then
  usage
  exit 1
fi

if [[ "$arg" = /* ]]; then
  round="$arg"
else
  round="${REPO_ROOT}/${arg}"
  [[ -f "$round" ]] || round="$arg"
fi

if [[ ! -f "$round" ]]; then
  echo "FAIL: file not found: $arg" >&2
  usage
  exit 1
fi

awk '
function trim(s){ gsub(/^[[:space:]]+|[[:space:]]+$/,"",s); return s }
function fail(msg){ print "FAIL: " msg; errs++ }
function field(line,   v){ sub(/^[[:space:]]*-[[:space:]]*[^:]+:[[:space:]]*/, "", line); return trim(line) }

BEGIN {
  errs=0; fm_seen=0; in_fm=0; section=""
  fb=""; dp=""; ap=""; rv=""
  fb_count=0; ap_count=0; required_count=0
  split("chat email document-comment meeting ticket", ch, " ")
  for (i in ch) valid_channel[ch[i]]=1
  split("blocking concern suggestion question", tp, " ")
  for (i in tp) valid_type[tp[i]]=1
  split("accept reject modify defer", dc, " ")
  for (i in dc) valid_decision[dc[i]]=1
  split("open revising approved blocked", stt, " ")
  for (i in stt) valid_status[stt[i]]=1
  split("research research+plan research+plan+execute", md, " ")
  for (i in md) valid_mode[md[i]]=1
}

/^---[[:space:]]*$/ {
  fm_seen++
  if (fm_seen == 1) { in_fm=1; next }
  if (fm_seen == 2) { in_fm=0; next }
}

in_fm == 1 {
  if (match($0, /^slug:[[:space:]]*/))             slug=trim(substr($0, RLENGTH+1))
  if (match($0, /^round:[[:space:]]*/))            round_no=trim(substr($0, RLENGTH+1))
  if (match($0, /^candidate_digest:[[:space:]]*/)) digest=trim(substr($0, RLENGTH+1))
  if (match($0, /^mode:[[:space:]]*/))             mode=trim(substr($0, RLENGTH+1))
  if (match($0, /^status:[[:space:]]*/))           status=trim(substr($0, RLENGTH+1))
  next
}

# The prohibition is absolute: no review round authorizes execution, and the
# check runs over every line so it cannot be evaded by placing it off-section.
/Execution Authorized:[[:space:]]*[Yy][Ee][Ss]/ {
  fail("Execution Authorized: yes — a review round never authorizes execution (review-gate.md section 10)")
}

/^## Candidate Manifest[[:space:]]*$/ { sec_manifest=1; section="manifest"; next }
/^## Authorities[[:space:]]*$/        { sec_auth=1;     section="auth";     next }
/^## Reviewer Pack[[:space:]]*$/      { sec_pack=1;     section="pack";     next }
/^## Feedback[[:space:]]*$/           { sec_feedback=1; section="feedback"; next }
/^## Dispositions[[:space:]]*$/       { sec_disp=1;     section="disp";     next }
/^## Redlines[[:space:]]*$/           { sec_redline=1;  section="redline";  next }
/^## Re-Review[[:space:]]*$/          { sec_rereview=1; section="rereview"; next }
/^## Approvals[[:space:]]*$/          { sec_approve=1;  section="approve";  next }
/^## Gate Result[[:space:]]*$/        { sec_gate=1;     section="gate";     next }
/^## /                                { section="other"; next }

section == "manifest" {
  if ($0 ~ /^-[[:space:]]*Digest:/)       manifest_digest=field($0)
  if ($0 ~ /^-[[:space:]]*Immutable:/)    manifest_immutable=field($0)
  if ($0 ~ /^-[[:space:]]*Source Ledger:/) manifest_source=field($0)
  next
}

section == "auth" && /^\|/ {
  n=split($0, f, "|")
  if (n < 6) next
  aid=trim(f[2])
  if (aid == "Authority" || aid == "" || aid ~ /^-+$/) next
  auth_owner[aid]=trim(f[3])
  auth_rev[aid]=trim(f[5])
  auth_seen[aid]=1
  auth_count++
  if (auth_rev[aid] !~ /^[0-9]+$/) fail("authority " aid " revision must be an integer, got " auth_rev[aid])
  if (trim(f[4]) == "") fail("authority " aid " declares no fields")
  next
}

section == "pack" && /^### Reviewer[[:space:]]/ {
  line=$0
  match(line, /^### Reviewer[[:space:]]+/)
  rv=trim(substr(line, RLENGTH+1))
  sub(/[[:space:]].*$/, "", rv)
  pack_seen[rv]=1
  pack_order[++pack_count]=rv
  if (index(line, "required_approver") > 0)      { pack_role[rv]="required_approver"; required_count++ }
  else if (index(line, "consulted") > 0)          pack_role[rv]="consulted"
  else if (index(line, "advisory") > 0)           pack_role[rv]="advisory"
  else fail("reviewer " rv " has no role of required_approver, consulted, or advisory")
  next
}

section == "pack" && /^-[[:space:]]*Questions:/ { if (rv != "") pack_has_q[rv]=1; next }
section == "pack" && /^[[:space:]]+-[[:space:]]*Q[0-9]+:/ { if (rv != "") pack_qcount[rv]++; next }
section == "pack" && /^-[[:space:]]*Authority:/ { if (rv != "") pack_auth[rv]=field($0); next }

section == "feedback" && /^### F[0-9]+[[:space:]]*$/ {
  fb=trim(substr($0, 5))
  fb_seen[fb]=1
  fb_order[++fb_count]=fb
  next
}

section == "feedback" && fb != "" {
  if ($0 ~ /^-[[:space:]]*Reviewer:/)   fb_reviewer[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Channel:/)    fb_channel[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Provenance:/) fb_prov[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Against:/)    fb_against[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Field:/)      fb_field[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Type:/)       fb_type[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Verbatim:/)   fb_verbatim[fb]=field($0)
  if ($0 ~ /^-[[:space:]]*Normalized:/) fb_norm[fb]=field($0)
  next
}

section == "disp" && /^### D[0-9]+/ {
  line=$0
  dp=trim(substr(line, 5))
  sub(/[[:space:]].*$/, "", dp)
  if (match(line, /F[0-9]+[[:space:]]*$/)) {
    target=trim(substr(line, RSTART, RLENGTH))
    disp_for[target]=dp
    disp_target[dp]=target
  } else {
    fail("disposition " dp " does not name the feedback item it resolves (expected \"### " dp " -> F<n>\")")
  }
  disp_order[++disp_count]=dp
  next
}

section == "disp" && dp != "" {
  if ($0 ~ /^-[[:space:]]*Decided By:/)     disp_by[dp]=field($0)
  if ($0 ~ /^-[[:space:]]*Decision:/)       disp_decision[dp]=field($0)
  if ($0 ~ /^-[[:space:]]*Rationale:/)      disp_rationale[dp]=field($0)
  if ($0 ~ /^-[[:space:]]*Decision Delta:/) disp_delta[dp]=field($0)
  next
}

section == "approve" && /^### A[0-9]+/ {
  ap=trim(substr($0, 5))
  sub(/[[:space:]].*$/, "", ap)
  ap_order[++ap_count]=ap
  next
}

section == "approve" && ap != "" {
  if ($0 ~ /^-[[:space:]]*Reviewer:/)            ap_reviewer[ap]=field($0)
  if ($0 ~ /^-[[:space:]]*Role:/)                ap_role[ap]=field($0)
  if ($0 ~ /^-[[:space:]]*Approves Candidate:/)  ap_digest[ap]=field($0)
  if ($0 ~ /^-[[:space:]]*Authority Revisions:/) ap_revs[ap]=field($0)
  if ($0 ~ /^-[[:space:]]*At:/)                  ap_at[ap]=field($0)
  if ($0 ~ /^-[[:space:]]*Scope Limit:/)         ap_scope[ap]=field($0)
  next
}

section == "gate" {
  if ($0 ~ /^-[[:space:]]*Verdict:/)              gate_verdict=field($0)
  if ($0 ~ /^-[[:space:]]*Execution Authorized:/) gate_exec=field($0)
  next
}

END {
  if (fm_seen < 2) fail("missing or incomplete frontmatter block")
  if (slug == "") fail("frontmatter missing slug")
  if (round_no !~ /^[0-9]+$/) fail("frontmatter round must be an integer, got " round_no)
  if (digest !~ /^sha256:[0-9a-f]{64}$/) fail("frontmatter candidate_digest must be sha256:<64 hex>, got " digest)
  if (!(mode in valid_mode)) fail("frontmatter mode " mode " is not a known mode")
  if (!(status in valid_status)) fail("frontmatter status " status " is not open, revising, approved, or blocked")

  if (!sec_manifest) fail("missing section: ## Candidate Manifest")
  if (!sec_auth)     fail("missing section: ## Authorities")
  if (!sec_pack)     fail("missing section: ## Reviewer Pack")
  if (!sec_feedback) fail("missing section: ## Feedback")
  if (!sec_disp)     fail("missing section: ## Dispositions")
  if (!sec_redline)  fail("missing section: ## Redlines")
  if (!sec_rereview) fail("missing section: ## Re-Review")
  if (!sec_approve)  fail("missing section: ## Approvals")
  if (!sec_gate)     fail("missing section: ## Gate Result")

  if (manifest_digest != "" && digest != "" && manifest_digest != digest)
    fail("## Candidate Manifest digest " manifest_digest " does not match frontmatter candidate_digest " digest)
  if (manifest_immutable != "true") fail("## Candidate Manifest must record Immutable: true")
  if (manifest_source == "") fail("## Candidate Manifest must record the Source Ledger it was frozen from")

  if (auth_count < 1) fail("## Authorities table has no authority rows")
  if (required_count < 1) fail("## Reviewer Pack has no required_approver")

  for (i=1; i<=pack_count; i++) {
    r=pack_order[i]
    if (pack_auth[r] == "") fail("reviewer " r " is not bound to an authority")
    if (pack_role[r] != "advisory" && pack_qcount[r] < 1)
      fail("reviewer " r " got no targeted questions — a pack without questions is not a review request")
  }

  for (i=1; i<=fb_count; i++) {
    fid=fb_order[i]
    if (fb_reviewer[fid] == "") fail(fid " missing Reviewer")
    if (fb_channel[fid] == "") fail(fid " missing Channel")
    else if (!(fb_channel[fid] in valid_channel)) fail(fid " has unknown Channel " fb_channel[fid])
    if (fb_prov[fid] == "") fail(fid " missing Provenance — feedback without a durable source cannot be audited")
    if (fb_against[fid] !~ /^sha256:[0-9a-f]/) fail(fid " Against must name the candidate digest the reviewer saw, got " fb_against[fid])
    if (fb_field[fid] == "") fail(fid " missing Field")
    if (fb_type[fid] == "") fail(fid " missing Type")
    else if (!(fb_type[fid] in valid_type)) fail(fid " has unknown Type " fb_type[fid])
    if (fb_verbatim[fid] == "") fail(fid " missing Verbatim — the original wording is never dropped")
    if (fb_norm[fid] == "") fail(fid " missing Normalized")
    if (fb_type[fid] == "blocking" && !(fid in disp_for))
      fail(fid " is blocking but has no disposition")
  }

  for (i=1; i<=disp_count; i++) {
    d=disp_order[i]
    t=disp_target[d]
    if (t != "" && !(t in fb_seen)) fail(d " resolves " t ", which is not a feedback item in this round")
    if (disp_by[d] == "") fail(d " missing Decided By — dispositions are human decisions")
    if (disp_decision[d] == "") fail(d " missing Decision")
    else if (!(disp_decision[d] in valid_decision)) fail(d " has unknown Decision " disp_decision[d])
    if (disp_rationale[d] == "") fail(d " missing Rationale")
    if (disp_delta[d] == "") fail(d " missing Decision Delta (use \"none\" when the candidate is unchanged)")
  }

  for (i=1; i<=ap_count; i++) {
    a=ap_order[i]
    stale=0
    if (ap_reviewer[a] == "") fail(a " missing Reviewer")
    if (ap_role[a] == "") fail(a " missing Role")
    if (ap_at[a] == "") fail(a " missing At")
    # Candidate-bound: an approval given against another candidate is stale.
    if (ap_digest[a] == "") { fail(a " missing Approves Candidate"); stale=1 }
    else if (ap_digest[a] != digest) {
      fail(a " is stale — it approves " ap_digest[a] " but this round is " digest)
      stale=1
    }
    if (ap_scope[a] != "does-not-authorize-execution")
      fail(a " must carry Scope Limit: does-not-authorize-execution")
    if (ap_revs[a] == "") {
      fail(a " missing Authority Revisions")
      stale=1
    } else {
      nr=split(ap_revs[a], revs, ",")
      for (k=1; k<=nr; k++) {
        pair=trim(revs[k])
        if (pair == "") continue
        if (split(pair, pr, "@") != 2) { fail(a " authority revision " pair " must be <AUTHORITY>@<revision>"); stale=1; continue }
        aid=trim(pr[1]); arv=trim(pr[2])
        if (!(aid in auth_seen)) { fail(a " names authority " aid ", which is not in the ## Authorities table"); stale=1; continue }
        if (arv != auth_rev[aid]) {
          fail(a " is stale — approved under " aid "@" arv " but " aid " is now at revision " auth_rev[aid])
          stale=1
        }
      }
    }
    # Only a non-stale approval counts toward the gate.
    if (!stale && ap_role[a] == "required_approver" && ap_reviewer[a] != "") approved_by[ap_reviewer[a]]=1
    if (ap_reviewer[a] != "" && !(ap_reviewer[a] in pack_seen))
      fail(a " is from " ap_reviewer[a] ", who was not sent a reviewer pack")
  }

  if (gate_exec == "") fail("## Gate Result must record Execution Authorized")
  else if (gate_exec != "no") fail("## Gate Result Execution Authorized must be no, got " gate_exec)
  if (gate_verdict == "") fail("## Gate Result must record a Verdict")

  if (status == "approved") {
    for (i=1; i<=pack_count; i++) {
      r=pack_order[i]
      if (pack_role[r] == "required_approver" && !(r in approved_by))
        fail("status is approved but required approver " r " has no non-stale approval in this round")
    }
    if (gate_verdict !~ /^approved-for-/)
      fail("status is approved but Verdict is " gate_verdict)
  }

  if (errs == 0) {
    printf "OK: review round %s valid (%d feedback, %d dispositions, %d approvals, %d required approvers, verdict %s)\n", \
      round_no, fb_count, disp_count, ap_count, required_count, gate_verdict
    exit 0
  }
  exit 1
}
' "$round"
