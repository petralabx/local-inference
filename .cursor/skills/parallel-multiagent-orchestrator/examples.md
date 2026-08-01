# Parallel Multiagent Orchestrator — Worked Examples

End-to-end transcripts showing how the N-candidate spawn, scope-lock, scoring, and winner selection actually play out. Start here after reading [SKILL.md](SKILL.md).

## A. To-Dos Loop 2, 2 parallel candidates (default N=2)

**Trigger:** `run parallel candidates for todos loop 02`

**Branch state:** `~/agentic-swarm-autoresearch-todos/` on `autoresearch/todos/loop-02` (cut from `autoresearch/todos` after Loop 1 baseline freeze).

### A.1 Preconditions

```bash
cd ~/agentic-swarm-autoresearch-todos/
test -f eval/ownership.json
test -f eval/models.json
test -f eval/baseline.json
test -f research/loop-02/hypotheses.md
```

Given `hypotheses.md`:

```markdown
# Hypotheses — Loop 2 (todos)

## H01 [tag: mechanical]
Extract todos router validation into zod schemas.
Expected pillar impact: schema_valid_response +0.001.

## H02 [tag: deep]
SharePoint sync p95 latency is driven by serial list enumeration; replace with
Graph `$batch` API. Expected pillar impact: sharepoint_sync_ms p95 -500.
```

### A.2 Schema-first VMC context

```bash
# Read descriptors before any CallMcpTool
for t in vmc_get_context vmc_checkout_task vmc_report_progress vmc_complete_task; do
  cat ~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/$t.json >/dev/null
done
```

```
CallMcpTool vmc_get_context args={"depth":"full","project":"autoresearch"}
CallMcpTool vmc_checkout_task args={"todoId":"ar-todos-l02"}
```

### A.3 Derive executor per hypothesis

```bash
jq -r '.executor_by_tag.mechanical' eval/models.json   # -> composer-2-fast
jq -r '.executor_by_tag.deep'       eval/models.json   # -> claude-opus-4-7-thinking-high
```

### A.4 Create per-hypothesis branches

```bash
git checkout -b autoresearch/todos/loop-02/hyp-01 autoresearch/todos/loop-02
git checkout autoresearch/todos/loop-02
git checkout -b autoresearch/todos/loop-02/hyp-02 autoresearch/todos/loop-02
git checkout autoresearch/todos/loop-02
```

### A.5 Spawn 2 best-of-n-runners in parallel

```
Task subagent_type=best-of-n-runner
     description="exec H01 mechanical todos L02"
     model=composer-2-fast
     run_in_background=true
     prompt="Execute hypothesis H01 on branch autoresearch/todos/loop-02/hyp-01.
             Scope: eval/ownership.json (owns + consumes_readonly only).
             Forbidden: any file matching eval/ownership.json .forbidden.
             Required artifacts at research/loop-02/hyp-01/:
               - ../../patches/hyp-01.patch (git diff against autoresearch/todos/loop-02)
               - NOTES.md, commands.log
             Do own vmc_checkout_task for todoId=ar-todos-l02-h01 before first edit.
             Do own vmc_report_progress at midpoint.
             Do NOT run eval/harness.ts --mode=score yourself; the orchestrator scores.
             Do NOT merge; produce the diff only.
             Stop after 4 failed attempts and write research/loop-02/hyp-01/BLOCKER.md."

Task subagent_type=best-of-n-runner
     description="exec H02 deep todos L02"
     model=claude-opus-4-7-thinking-high
     run_in_background=true
     prompt="[same template, H02, branch hyp-02, todoId ar-todos-l02-h02]"
```

### A.6 Scope-lock each candidate

```bash
for M in 01 02; do
  .cursor/hooks/scope-lock.sh todos research/loop-02/patches/hyp-$M.patch \
    && echo "hyp-$M: scope-lock OK" \
    || echo "hyp-$M: REJECTED"
done
```

Suppose `hyp-01` passes, `hyp-02` passes.

### A.7 Score each + null-hypothesis control arm

```bash
for M in 01 02; do
  git checkout autoresearch/todos/loop-02/hyp-$M
  npm test -- todos-contracts
  npx tsx eval/harness.ts --mode=score --candidate=hyp-$M \
    --out=research/loop-02/scorecard-hyp-$M.json
done

git checkout autoresearch/todos/loop-02
npx tsx eval/harness.ts --mode=score --candidate=null \
  --out=research/loop-02/scorecard-null.json
```

### A.8 Cross-domain regression check

```bash
for d in chat second-brain swarm; do
  npm test -- $d-contracts || { echo "CROSS_DOMAIN_REGRESSION in $d"; exit 1; }
done
```

### A.9 Winner selection

```bash
scripts/pick-winner.sh \
  --loop=02 \
  --domain=todos \
  --scorecards=research/loop-02/scorecard-hyp-*.json \
  --null=research/loop-02/scorecard-null.json \
  --baseline=eval/baseline.json \
  --out=research/loop-02/REPORT.md
```

Suppose `hyp-02` wins with `loop_score=4.7` (sharepoint p95 improved from 1180 -> 640, ~4.7 variance units). `hyp-01` stays within variance on schema_valid_response and is marked `rejected-score`.

### A.10 Merge winner + VMC close

```bash
git checkout autoresearch/todos/loop-02
git merge --no-ff autoresearch/todos/loop-02/hyp-02
git commit -m "feat(autoresearch-todos): loop 02 winner hyp-02 (deep)"
```

```
CallMcpTool vmc_report_progress args={
  "todoId": "ar-todos-l02",
  "progressPct": 100,
  "phase": "loop-2-complete",
  "evidence": "Winner hyp-02 (deep). sharepoint_sync_ms p95: 1180 -> 640 (-4.7 var). H01 rejected-score. No cross-domain regressions."
}
CallMcpTool vmc_complete_task args={
  "todoId": "ar-todos-l02",
  "evidence": "See research/loop-02/REPORT.md",
  "commitSha": "<merge-sha>",
  "filesChanged": ["research/loop-02/REPORT.md", "portal/src/lib/todos/sharepoint-sync.ts", "..."]
}
CallMcpTool vmc_complete_task args={ "todoId": "ar-todos-l02-h01", "evidence": "rejected-score; delta within null variance" }
CallMcpTool vmc_complete_task args={ "todoId": "ar-todos-l02-h02", "evidence": "winner; merged into autoresearch/todos/loop-02" }
```

## B. Scope-Lock Rejection

**Scenario:** Loop 3 hypothesis H02 (tag `deep`) proposes optimizing SharePoint sync but the `best-of-n-runner` touched `portal/src/lib/chat/message-queue.ts` to "share a helper". That file is listed in `eval/ownership.json.forbidden` for the `todos` domain.

### B.1 Scope-lock run

```bash
$ .cursor/hooks/scope-lock.sh todos research/loop-03/patches/hyp-02.patch
SCOPE_LOCK_VIOLATION forbidden: portal/src/lib/chat/message-queue.ts
$ echo $?
2
```

### B.2 Archive + record

```bash
mkdir -p research/loop-03/rejected/hyp-02
mv research/loop-03/patches/hyp-02.patch research/loop-03/rejected/hyp-02/patch.diff
echo "SCOPE_LOCK_VIOLATION forbidden: portal/src/lib/chat/message-queue.ts" \
  > research/loop-03/rejected/hyp-02/reason.txt
```

### B.3 REPORT.md entry

```markdown
## Candidates

| Hyp | Tag | Executor | Branch | Status | loop_score |
|---|---|---|---|---|---|
| H01 | moderate | composer-2-fast | .../loop-03/hyp-01 | winner | 2.3 |
| H02 | deep    | claude-opus-4-7-thinking-high | .../loop-03/hyp-02 | rejected-scope | n/a |
```

### B.4 Auto-escalation? No.

Scope-lock rejection is **not** a gate failure that triggers auto-escalation — it's a hypothesis-execution failure. Auto-escalation is reserved for cases where the model tier was genuinely under-powered for the hypothesis, not cases where the agent went out of bounds. Record the rejection and, if H02's hypothesis is still viable, restate it in `research/loop-04/hypotheses.md` with a sharper scope reminder.

## C. Skill Regression — Mock Loop

The skill's own smoke test. Intended to prove the skill loads correctly and the scope-lock script actually rejects an out-of-scope patch.

### C.1 Run

```bash
bash ~/.cursor/skills/parallel-multiagent-orchestrator/scripts/mock-loop.sh
```

Expected output (abridged):

```
[mock-loop] workdir: /tmp/parallel-orch-mock-XXXXXX
[mock-loop] ownership.json written
[mock-loop] hyp-01 patch: in-scope (touches domain/owns_me.txt)
[mock-loop] hyp-02 patch: out-of-scope (touches other-domain/forbidden_me.txt)
[mock-loop] scope-lock hyp-01 ... OK
[mock-loop] scope-lock hyp-02 ... REJECTED (exit=2, reason=forbidden)
[mock-loop] scorecards written: hyp-01, hyp-02, null
[mock-loop] pick-winner ... winner=hyp-01 loop_score=3.5
[mock-loop] REPORT.md written
[mock-loop] EXIT CRITERIA MET:
  ✓ 2 parallel candidates processed
  ✓ scope-lock rejected 1 out-of-scope candidate
  ✓ scorecard produced
  ✓ REPORT.md declares winner with rubric evidence
```

### C.2 What it proves

Exit criteria from plan Phase 3 and user's Phase 3 task:

1. **Skill loads via trigger phrase** — verified when an agent loads `SKILL.md` on phrase match and the `description` field is present with the listed triggers.
2. **Mock loop with 2 parallel candidates completes and produces a scorecard** — `mock-loop.sh` runs both candidates through scope-lock + scoring + pick-winner and writes deterministic scorecards.
3. **Scope-lock rejects an out-of-scope patch** — `hyp-02` in the mock touches `other-domain/forbidden_me.txt`, listed in `forbidden`; scope-lock exits 2.

No VMC MCP call is made in the mock (no network, no auth) — the skill-regression test intentionally keeps the tooling surface local to avoid flaking on credential changes.

## D. Auto-Escalation

**Scenario:** Loop 2 and Loop 3 both run `H02` tagged `moderate` with `composer-2-fast`. Both times the candidate scored below null-hypothesis variance on the target pillar. The orchestrator trips the auto-escalation rule.

### D.1 Trigger

The orchestrator walks `research/loop-02/REPORT.md` and `research/loop-03/REPORT.md` looking for `failure_reason` on the same hypothesis line. Two consecutive failures → auto-escalate.

### D.2 Entry in `research/loop-04/REPORT.md`

```yaml
## Auto-Escalations
- hypothesis: H02
  original_tag: moderate
  original_executor: composer-2-fast
  failures:
    - loop: 02
      failure_reason: "below null-hypothesis variance (delta=0.4 < 1.0)"
    - loop: 03
      failure_reason: "below null-hypothesis variance (delta=0.6 < 1.0)"
  escalated_at: 2026-04-25T09:12:00Z
  new_tag: deep
  new_executor: claude-opus-4-7-thinking-high
  eval_models_json_note: "auto-escalated per skill §4"
```

### D.3 eval/models.json override (additive only)

```json
{
  "executor_by_tag": { "mechanical": "composer-2-fast", "moderate": "composer-2-fast", "deep": "claude-opus-4-7-thinking-high" },
  "per_hypothesis_overrides": {
    "l04-h02": { "executor": "claude-opus-4-7-thinking-high", "reason": "auto-escalated after 2 failures" }
  }
}
```

### D.4 Stop if pile-up

If `auto_escalations >= 3` in a single loop, trip the orchestrator-specific hard stop: too many hypotheses mis-tagged at generation time. Halt and ask the hypothesis generator to re-tag the whole loop's hypotheses before continuing.

## E. Stop Condition — `all_candidates_rejected`

**Scenario:** In Loop 3 both `hyp-01` and `hyp-02` fail the rubric: `hyp-01` fails cross-domain regression (touches swarm somehow), `hyp-02` is rejected for scope-lock violation.

### E.1 Result

```markdown
# BLOCKER — todos loop 03

- **Condition fired:** all_candidates_rejected
- **Detected at:** 2026-04-25T11:43:00Z
- **Evidence:**
  - research/loop-03/rejected/hyp-01/: cross-domain swarm-contracts failed
  - research/loop-03/rejected/hyp-02/: scope-lock forbidden: portal/src/lib/chat/**
- **Recommended next action:** Re-generate Loop 3 hypotheses with tighter scope hints. Consider widening `eval/ownership.json.owns` if the blocker is structural rather than drift.
- **Human required:** true
```

No `vmc_complete_task` — the parent loop todoId stays `in_progress` until a human decides whether to retry, widen scope, or stop the domain.

## Trigger Phrase Reference

| Phrase | Action |
|---|---|
| `run parallel candidates for <domain> loop <N>` | Spawn all hypotheses from `research/loop-<N>/hypotheses.md` |
| `spawn best-of-n for <domain> loop <N>` | Same as above |
| `pick winner for <domain> loop <N>` | Score existing candidates + run pick-winner.sh; emit REPORT.md |
| `auto-escalate <domain> h<M>` | Manual trigger of the auto-escalation path for one hypothesis |
| `orchestrator mock loop` | Run `scripts/mock-loop.sh` for skill regression |
