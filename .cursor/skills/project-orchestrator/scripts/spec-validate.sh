#!/usr/bin/env bash
#
# spec-validate.sh — validate a Project Orchestrator SPEC.md before approval.
#
# Usage: spec-validate.sh <path/to/SPEC.md>
#
# Checks: required sections present; phase ids unique; every depends_on references an
# existing phase; every phase has non-empty owns + acceptance; dependency graph is
# acyclic (topological sort). Exit 0 if valid, 1 otherwise.

set -uo pipefail

spec="${1:-}"
if [[ -z "$spec" || ! -f "$spec" ]]; then
  echo "usage: spec-validate.sh <path/to/SPEC.md>" >&2
  exit 64
fi

awk '
function trim(s){ gsub(/^[[:space:]]+|[[:space:]]+$/,"",s); return s }

/^## Mission/          { sec_mission=1 }
/^## Success Criteria/ { sec_success=1 }
/^## Phases/           { sec_phases=1 }
/^## Worktree Plan/    { sec_worktree=1 }

/^### *P[0-9]+/ {
  match($0, /P[0-9]+/); id=substr($0, RSTART, RLENGTH)
  cur=id; count[id]++; order[++n]=id
  next
}

cur != "" && /^- *depends_on:/ {
  line=$0; sub(/^- *depends_on:[[:space:]]*/,"",line)
  gsub(/[\[\]]/,"",line)
  depstr[cur]=trim(line)
  next
}
cur != "" && /^- *owns:/ {
  line=$0; sub(/^- *owns:[[:space:]]*/,"",line)
  gsub(/[\[\][:space:]"]/,"",line)
  if (length(line) > 0) has_owns[cur]=1
  next
}
cur != "" && /^- *acceptance:/ {
  line=$0; sub(/^- *acceptance:[[:space:]]*/,"",line)
  gsub(/[`[:space:]]/,"",line)
  if (length(line) > 0) has_acc[cur]=1
  next
}

END {
  errs=0
  if (!sec_mission)  { print "FAIL: missing section ## Mission"; errs++ }
  if (!sec_success)  { print "FAIL: missing section ## Success Criteria"; errs++ }
  if (!sec_phases)   { print "FAIL: missing section ## Phases"; errs++ }
  if (!sec_worktree) { print "FAIL: missing section ## Worktree Plan"; errs++ }
  if (n == 0)        { print "FAIL: no phases (### P<k>) found"; errs++ }

  for (id in count) if (count[id] > 1) { print "FAIL: duplicate phase id " id; errs++ }

  for (i=1; i<=n; i++) {
    id=order[i]
    if (!has_owns[id]) { print "FAIL: " id " has empty/missing owns"; errs++ }
    if (!has_acc[id])  { print "FAIL: " id " has empty/missing acceptance"; errs++ }
    indeg[id]=0
  }

  # validate dep references + build graph
  for (i=1; i<=n; i++) {
    id=order[i]
    if (depstr[id]=="" ) continue
    m=split(depstr[id], d, /,/)
    for (j=1;j<=m;j++) {
      dep=d[j]; gsub(/[[:space:]]/,"",dep)
      if (dep=="") continue
      if (!(dep in count)) { print "FAIL: " id " depends_on unknown phase " dep; errs++; continue }
      adj[dep]=adj[dep] " " id   # edge dep -> id
      indeg[id]++
    }
  }

  # Kahn topological sort for cycle detection
  qn=0
  for (i=1;i<=n;i++){ id=order[i]; if (indeg[id]==0) queue[++qn]=id }
  processed=0; head=1
  while (head<=qn) {
    u=queue[head++]; processed++
    sp=split(adj[u], outs, /[[:space:]]+/)
    for (k=1;k<=sp;k++){ v=outs[k]; if (v=="") continue; if (--indeg[v]==0) queue[++qn]=v }
  }
  if (processed < n) { print "FAIL: dependency cycle detected among phases"; errs++ }

  if (errs==0) { print "OK: " n " phases, ids unique, deps resolve, DAG acyclic, owns+acceptance present" }
  exit(errs==0 ? 0 : 1)
}
' "$spec"
