# VMC AutoResearch Core — Worked Examples

End-to-end transcripts showing how the 5-loop contract actually plays out. Start here when you've read [SKILL.md](SKILL.md) and want to see the motions before invoking the first trigger.

## Example A: To-Dos pilot, Loop 0 (Investigation)

**Trigger:** `start autoresearch for todos`

**Branch state:** `~/agentic-swarm-autoresearch-todos/` on `autoresearch/todos` cut from `staging`.

### 1) Schema-first context fetch

```bash
# Read descriptors first (no CallMcpTool before this)
cat ~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/vmc_get_context.json
cat ~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/vmc_get_roadmap.json
cat ~/.cursor/projects/home-vinnysachet/mcps/user-vmc-context/tools/vmc_checkout_task.json
```

Then:

```
CallMcpTool server=user-vmc-context tool=vmc_get_context args={"depth":"full","project":"autoresearch"}
CallMcpTool server=user-vmc-context tool=vmc_get_roadmap  args={"project":"autoresearch"}
```

Identify `todoId` for "autoresearch todos loop 0 investigation" — say it's `ar-todos-l0`.

```
CallMcpTool server=user-vmc-context tool=vmc_checkout_task args={"todoId":"ar-todos-l0"}
```

### 2) Bootstrap eval/ scaffold

```bash
~/.cursor/skills/vmc-autoresearch-core/scripts/init-eval.sh todos ~/agentic-swarm-autoresearch-todos/
```

This creates (skeleton) `eval/ownership.json`, `eval/models.json`, `eval/scorecard.md`, `eval/fixtures/`, `eval/harness.ts`. Edit `ownership.json` to pin the exact To-Dos file globs.

### 3) Scoped codebase investigation

Use `explore` subagent with `readonly=true` and scope limited to `owns` + `consumes_readonly` globs:

```
Task subagent_type=explore readonly=true prompt="Investigate all files listed in eval/ownership.json .owns for the To-Dos domain. Produce research/loop-00/investigation.md with: (1) component map, (2) I/O contracts, (3) known bug reports from git log --grep=todo, (4) observed reliability weak points, (5) proposed pillars. Do not read files outside ownership globs."
```

### 4) Loop 0 gate

```bash
cd ~/agentic-swarm-autoresearch-todos/
jq '.' eval/ownership.json >/dev/null
rg -l -f <(jq -r '.forbidden[]' eval/ownership.json) research/loop-00/investigation.md && {
  echo "SCOPE_LOCK_VIOLATION in investigation"
  exit 1
}
```

### 5) Report + advance

```
CallMcpTool vmc_report_progress args={
  "todoId": "ar-todos-l0",
  "progressPct": 100,
  "phase": "loop-0-complete",
  "evidence": "research/loop-00/investigation.md committed; ownership.json verified; no forbidden-glob references"
}
CallMcpTool vmc_complete_task args={
  "todoId": "ar-todos-l0",
  "evidence": "Loop 0 investigation complete for todos domain.",
  "commitSha": "abc1234",
  "filesChanged": [
    "eval/ownership.json",
    "eval/models.json",
    "eval/scorecard.md",
    "research/loop-00/investigation.md"
  ]
}
```

## Example B: To-Dos pilot, Loop 1 (Baseline freeze)

**Trigger:** `run autoresearch loop 1 for todos` (after loop 0 gate green)

### 1) Prep

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
# Verify we're on staging DB, not production:
echo "$DATABASE_URL" | grep plx-postgres-staging || { echo "WRONG DB"; exit 1; }
```

### 2) Seed fixtures + holdout

```bash
# Seeded prompts (agent-visible)
npx tsx eval/generate-fixtures.ts --domain=todos --n=200 --out=eval/fixtures/

# Holdout (agent-blind): insert directly to Postgres
npx tsx eval/seed-holdout.ts --domain=todos --n=100
```

Holdout seeding uses `plx_autoresearch_verifier` role and NEVER returns row contents to the agent.

### 3) Run baseline harness

```bash
npx tsx eval/harness.ts --mode=baseline --out=eval/baseline.json --n=300
sha256sum eval/baseline.json > eval/baseline.json.sha256
```

Baseline captures per-pillar p50/p95/p99 + null-hypothesis variance.

### 4) Tag baseline

```bash
git add eval/
git commit -m "feat(autoresearch-todos): loop 1 baseline freeze"
git tag autoresearch/todos-baseline-$(date -u +%Y%m%dT%H%MZ)
```

### 5) Loop 1 gate + report

```bash
npm test -- todos-contracts
```

```
CallMcpTool vmc_complete_task args={
  "todoId": "ar-todos-l1",
  "evidence": "Baseline frozen. N=300. Tag autoresearch/todos-baseline-<ts>. Holdout rows in Postgres: 100.",
  "commitSha": "def5678",
  "filesChanged": ["eval/baseline.json", "eval/baseline.json.sha256"]
}
```

## Example C: To-Dos pilot, Loop 2 (Research run 1)

**Trigger:** `run autoresearch loop 2 for todos`

### 1) Hypothesis generation (frontier)

Frontier model reads `research/loop-00/investigation.md` + `eval/baseline.json` and emits `research/loop-02/hypotheses.md`:

```markdown
# Hypotheses — Loop 2

## H1 [tag: mechanical]
Refactor todos router to extract validation into zod schemas.
Expected pillar impact: schema_valid_response +0.001 (small).

## H2 [tag: deep]
SharePoint sync p95 latency is driven by serial list enumeration. Replace with
batched $batch API calls (Graph v1.0). Pillar: sharepoint_sync_ms p95 -500.

## H3 [tag: moderate]
Roadmap parity drift caused by eventual-consistency race between portal write and
VMC checkout_task. Add read-after-write verification. Pillar: roadmap_parity_pct +0.005.
```

Tags determine executor per `eval/models.json`.

### 2) Parallel candidate execution (via parallel-multiagent-orchestrator skill)

Three `best-of-n-runner` subagents spawn in parallel, each on its own branch:

```
Task subagent_type=best-of-n-runner prompt="Execute H1 on autoresearch/todos/loop-02/hyp-01 using composer-2-fast. Scope-lock via eval/ownership.json. Produce diff only."
Task subagent_type=best-of-n-runner prompt="Execute H2 on autoresearch/todos/loop-02/hyp-02 using claude-opus-4-7-thinking-high (deep tag). Scope-lock via eval/ownership.json."
Task subagent_type=best-of-n-runner prompt="Execute H3 on autoresearch/todos/loop-02/hyp-03 using composer-2-fast + frontier scorecard review (moderate tag)."
```

### 3) Score each candidate + null arm

```bash
for hyp in hyp-01 hyp-02 hyp-03; do
  git checkout autoresearch/todos/loop-02/$hyp
  npm test -- todos-contracts
  npx tsx eval/harness.ts --mode=score --candidate=$hyp --out=research/loop-02/scorecard-$hyp.json
done

# Null-hypothesis control arm: re-run unchanged baseline
git checkout autoresearch/todos
npx tsx eval/harness.ts --mode=score --candidate=null --out=research/loop-02/scorecard-null.json
```

### 4) Cross-domain regression check

```bash
for d in chat second-brain swarm; do
  npm test -- $d-contracts || { echo "CROSS_DOMAIN_REGRESSION in $d"; exit 1; }
done
```

### 5) Scope-lock enforcement (per candidate)

```bash
for hyp in hyp-01 hyp-02 hyp-03; do
  .cursor/hooks/scope-lock.sh todos research/loop-02/$hyp.patch || {
    echo "$hyp rejected: scope-lock violation"
    continue
  }
done
```

### 6) Winner selection + REPORT.md

```bash
# Pick max loop_score passing all gates
npx tsx eval/pick-winner.ts --loop=02 --out=research/loop-02/REPORT.md
```

Winner merges into `autoresearch/todos/loop-02`. Rejected candidates archived under `research/loop-02/rejected/`.

### 7) Report progress

```
CallMcpTool vmc_report_progress args={
  "todoId": "ar-todos-l2",
  "progressPct": 100,
  "phase": "loop-2-complete",
  "evidence": "Winner: hyp-02 (deep). sharepoint_sync_ms p95: 1180 -> 640 (-4.7 variance units). No cross-domain regressions. H1 rejected (below null-hypothesis variance). H3 rejected (scope-lock: touched portal/src/lib/vmc/core — readonly)."
}
```

## Example D: Stop condition fired

**Scenario:** Loop 3 completes, no pillar improved beyond variance. Loop 4 also stagnant.

Skill detects `stagnant_loops >= 2` and halts before Loop 4 research begins.

```markdown
# BLOCKER — todos loop 04

- **Condition fired:** stagnant_loops >= 2
- **Detected at:** 2026-04-24T11:23:00Z
- **Evidence:**
  - research/loop-02/REPORT.md loop_score = 3.2 (winner hyp-02)
  - research/loop-03/REPORT.md loop_score = 0.4 (within variance)
  - research/loop-04/REPORT.md loop_score = -0.1 (within variance)
- **Recommended next action:** Ceiling likely reached for sharepoint_sync_ms under current Graph API. Human decision: (a) accept loop-02 winner as final and skip to Loop 5 with reduced scope, or (b) expand ownership.json to include `portal/src/lib/graph-client/**` and retry with wider optimization space.
- **Human required:** true
```

`vmc_report_progress` called with `phase="blocked"` and link to this BLOCKER.md. No further loops run until a human decides.

## Example E: Holdout leak tripwire

**Scenario:** During Loop 5 final merge gate, verifier runs:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM autoresearch_holdout WHERE seen_by_agent_at IS NOT NULL;"
```

Returns `3`. The holdout was accidentally exposed to a research agent (e.g., via a fixture loader bug).

**Result:** Merge blocks immediately. `BLOCKER.md` written with `holdout_leak_detected: true`. Every metric from loops where the leak was possible is invalidated. Rebuild from the baseline tag with a fresh holdout set.

## Example F: VMC MCP auth failure (real, observed 2026-04-23)

**Scenario:** Phase 1 build session. `vmc_get_context` returned `Invalid or missing API key`.

**Correct response (what this skill requires):**

1. Halt VMC-dependent actions immediately.
2. Document the blocker in the phase report.
3. Proceed only with work that does NOT require VMC state (e.g., authoring the skill file itself).
4. Do NOT fabricate `vmc_report_progress` / `vmc_complete_task` evidence.
5. On session restart with auth fixed: replay the missing `vmc_checkout_task` / `vmc_complete_task` calls with retroactive `notes` documenting the delay.

## Trigger Phrase Reference

| Phrase | Action |
|---|---|
| `start autoresearch for <domain>` | Enter the skill; verify branch; bootstrap eval/ if absent; begin Loop 0 |
| `run autoresearch loop <N> for <domain>` | Execute loop N per state machine |
| `autoresearch status for <domain>` | Read-only: latest REPORT.md + current todoId + pending gates |
| `autoresearch merge gate <domain>` | Present MERGE_GATE.md checklist for Vince's signature |
| `autoresearch rollback <domain>` | Invoke `scripts/autoresearch-rollback.sh` to the last baseline tag |
