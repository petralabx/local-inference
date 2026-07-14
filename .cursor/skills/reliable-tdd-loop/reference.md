# Reliable TDD Loop — Reference

Full schemas, gate commands, hook script contents, and null-hypothesis math. Load on demand from [SKILL.md](SKILL.md).

## 1. Domain Contract File Registry

The skill only accepts tests added to these files:

| Domain | Contract file | Owner eval manifest |
|---|---|---|
| `todos` | `apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts` | `~/agentic-swarm-autoresearch-todos/eval/ownership.json` |
| `chat` | `apps/vmc-web/src/lib/vmc/__tests__/routes/chat-contracts.test.ts` | `~/agentic-swarm-autoresearch-chat/eval/ownership.json` |
| `swarm` | `apps/vmc-web/src/lib/vmc/__tests__/routes/swarm-contracts.test.ts` | `~/agentic-swarm-autoresearch-swarm/eval/ownership.json` |
| `second-brain` | `apps/vmc-web/src/lib/vmc/__tests__/routes/second-brain-contracts.test.ts` | `~/agentic-swarm-autoresearch-second-brain/eval/ownership.json` |

Any test added to `reliability-contracts.test.ts` (the legacy catch-all) is a **scope violation** and the `beforeShellExecution` hook emits an advisory `user_message`.

## 2. Iteration Report Schema (`research/loop-<N>/tdd-<K>.md`)

Every iteration writes one markdown file. The skill parses the `Null-hypothesis control arm` block to gate advancement.

```markdown
# TDD iteration <K> — domain=<DOMAIN> loop=<N>

## Hypothesis
<one sentence: what behavior is asserted, what contract gap it closes>

## Tag
mechanical | moderate | deep

## Red
- file: apps/vmc-web/src/lib/vmc/__tests__/routes/<domain>-contracts.test.ts
- test_name: "<describe > it name>"
- command: npm test -- <domain>-contracts
- exit_code: 1
- failure_reason: <assertion excerpt; NOT import error / syntax>
- red_commit_sha: <sha>

## Green
- implementation_files:
  - <file 1>
  - <file 2>
- command: npm test -- <domain>-contracts
- exit_code: 0
- green_commit_sha: <sha>
- diff_stat: <N files changed, +A -D>

## Null-hypothesis control arm
- baseline_commit: <sha before this iteration>
- pillar: <pillar key from eval/baseline.json.pillars>
- baseline_frozen_metric: <value from eval/baseline.json>
- rerun_metric: <value from re-running harness on baseline this iteration>
- candidate_metric: <value from harness on green commit>
- variance_unit: <value from eval/baseline.json.null_hypothesis_variance[pillar]>
- delta_candidate_vs_baseline_frozen: <candidate - baseline_frozen>
- delta_rerun_vs_baseline_frozen: <rerun - baseline_frozen>     # noise estimate
- z_score = (candidate - baseline_frozen) / variance_unit
- verdict: accept | null-result | regression

Advancement rule:
- |z_score| >= 1.0 AND verdict == "accept" => advance to refactor step
- otherwise => treat iteration as null result; do NOT merge

## Refactor
- command: npm test -- <domain>-contracts
- exit_code: 0
- refactor_commit_sha: <sha>
- behavior_unchanged_evidence: <diff narrative — only structure, not semantics>

## Tier-2 gate (run once per completed iteration)
- validate_sh_exit: <0|nonzero>
- cross_domain_suite_exit: <0|nonzero>
- other_domain_contracts_exits:
  - todos-contracts: <0|nonzero>
  - chat-contracts: <0|nonzero>
  - swarm-contracts: <0|nonzero>
  - second-brain-contracts: <0|nonzero>

## VMC coordination
- todoId: <from vmc_get_roadmap>
- progress_reports: [<timestamp list>]
- complete_task_called_at: <timestamp or null>

## Scope-lock audit
- files_changed: [<list from git diff --name-only baseline..refactor_commit_sha>]
- violations: [<files not matching eval/ownership.json.owns>]
```

## 3. `.cursor/hooks.json` Schema (canonical)

Project-root hooks file. Schema version 1.

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": ".cursor/hooks/tdd-gate.sh",
        "matcher": "npm test -- .*-contracts",
        "failClosed": false,
        "timeout": 10
      }
    ],
    "subagentStop": [
      {
        "command": ".cursor/hooks/verifier-rerun.sh",
        "failClosed": false,
        "timeout": 30,
        "loop_limit": 2
      }
    ]
  }
}
```

Matcher notes:

- The regex is JavaScript-flavor (not POSIX). `.*-contracts` is intentional: it matches any `<domain>-contracts` invocation including `reliability-contracts` so the gate can emit the scope-violation advisory.
- `failClosed: false` is intentional — the hook is advisory. A broken hook should never block a legitimate `npm test`. Scope violations are reported via `user_message` + `agent_message` and by writing `research/loop-*/BLOCKER-tdd-*.md` when invoked from inside an autoresearch branch.
- `subagentStop` has no matcher: it evaluates every subagent termination but exits 0 quickly when no dangling TDD iteration marker is present. `loop_limit: 2` caps how many times it can chain to re-run the verifier per session.

## 4. Hook Script Contracts

Canonical hook scripts live **once** at `.cursor/hooks/*.sh` (the path `hooks.json` executes). The skill's own `scripts/` directory intentionally does **not** contain duplicates — links below point to the single source of truth to avoid drift.

### `.cursor/hooks/tdd-gate.sh`

Advisory gate on `npm test -- <domain>-contracts`.

Input (stdin JSON per Cursor beforeShellExecution spec):

```json
{ "command": "npm test -- todos-contracts", "cwd": "/home/vinnysachet/..." }
```

Behavior:

1. Parse `command`.
2. Allow unconditionally if it does not match `npm test -- .*-contracts`.
3. If it targets `reliability-contracts` (the deprecated catch-all), emit a permission=`ask` response with an advisory `user_message` explaining the domain-specific contract file pattern.
4. Otherwise, if inside an `autoresearch/<domain>` branch, verify that `eval/ownership.json` exists and that the expected `<domain>-contracts.test.ts` path is declared in `.owns`. If missing, emit advisory warning.
5. Always `exit 0` (fail-open by design); only `permission=ask` on clear scope violation.

Output (stdout JSON):

```json
{ "permission": "allow" }
```

or

```json
{
  "permission": "ask",
  "user_message": "Running against deprecated generic reliability-contracts; this skill requires a per-domain <domain>-contracts.test.ts file.",
  "agent_message": "reliable-tdd-loop advisory: target a per-domain contract file; do not extend reliability-contracts.test.ts."
}
```

Full source (canonical, single location): [`../../hooks/tdd-gate.sh`](../../hooks/tdd-gate.sh).

### `.cursor/hooks/verifier-rerun.sh`

Auto-rerun Tier-1 on subagentStop when a TDD iteration marker indicates dangling red/green/refactor state.

Input (stdin JSON per Cursor subagentStop spec):

```json
{ "subagent_type": "generalPurpose", "session_id": "...", "cwd": "..." }
```

Behavior:

1. Look for markers in `research/loop-*/tdd-*.md` where the Green or Refactor block has no exit_code recorded.
2. If found, emit `followup_message` telling the main agent to re-run the Tier-1 command and update the iteration report.
3. If none found, `exit 0` silently.
4. `loop_limit: 2` in `hooks.json` ensures this cannot cycle indefinitely.

Output (stdout JSON):

```json
{ "followup_message": "Dangling TDD iteration detected at research/loop-02/tdd-01.md; re-run `npm test -- todos-contracts` and update the Green block with exit_code + green_commit_sha." }
```

Full source (canonical, single location): [`../../hooks/verifier-rerun.sh`](../../hooks/verifier-rerun.sh).

## 5. Tier-2 Gate Commands (exact)

Run from the domain worktree root. Paste output verbatim into `research/loop-<N>/tdd-<K>.md`.

```bash
# Prep
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh

# Full validation
bash scripts/validate.sh

# All domain contract suites (including this one, as a sanity check)
npm test -- todos-contracts
npm test -- chat-contracts
npm test -- swarm-contracts
npm test -- second-brain-contracts

# Cross-domain interface tests
npm test -- cross-domain

# Scope-lock audit for this iteration's diff
jq -r '.owns[]' eval/ownership.json > /tmp/owns.txt
git diff --name-only "$BASELINE_SHA..HEAD" > /tmp/changed.txt
while read f; do
  matched=0
  while read pat; do
    [[ "$f" == $pat ]] && { matched=1; break; }
  done < /tmp/owns.txt
  [[ $matched -eq 0 ]] && echo "SCOPE_LOCK_VIOLATION: $f"
done < /tmp/changed.txt
```

Any nonzero exit code in this block **blocks** `vmc_complete_task`.

## 6. Null-Hypothesis Math (canonical)

Every iteration re-runs the unchanged baseline under the same fixtures, harness, and models to establish the noise floor for that iteration's run. The skill compares the candidate against the **frozen** baseline (Loop 1) and uses the **rerun delta** as a noise estimator.

```
baseline_frozen_metric       = eval/baseline.json.pillars[<pillar>].p50
variance_unit                = eval/baseline.json.null_hypothesis_variance[<pillar>]
baseline_rerun_metric        = harness(--mode=score --candidate=null)
candidate_metric             = harness(--mode=score --candidate=tdd-<K>)

delta_candidate_vs_frozen    = candidate_metric - baseline_frozen_metric
delta_rerun_vs_frozen        = baseline_rerun_metric - baseline_frozen_metric   # noise estimate
z_score                      = delta_candidate_vs_frozen / variance_unit

verdict:
  accept       if |z_score| >= 1.0 AND sign(delta_candidate) matches "improvement" per pillar semantics
  null-result  if |z_score| <  1.0
  regression   if sign(delta_candidate) opposes improvement AND |z_score| >= 1.0
```

For pillars where "improvement" is a decrease (e.g. `sharepoint_sync_ms`), "improvement" means `candidate < baseline_frozen`.

If `|delta_rerun_vs_frozen| > 0.5 * variance_unit`, the harness is unstable — **halt** and reseed fixtures before continuing. Documented in `research/loop-<N>/BLOCKER-tdd-<K>.md`.

## 7. TodoWrite Item Templates

Use these exact content strings so the skill's subagentStop hook can parse them.

```json
[
  { "id": "tdd-<K>-red",      "content": "TDD iter <K> RED: write failing test in <domain>-contracts.test.ts; confirm RED for right reason", "status": "in_progress" },
  { "id": "tdd-<K>-green",    "content": "TDD iter <K> GREEN: minimal impl; npm test -- <domain>-contracts green",                           "status": "pending" },
  { "id": "tdd-<K>-refactor", "content": "TDD iter <K> REFACTOR: zero-behavior-change cleanup; Tier-1 green",                                "status": "pending" }
]
```

## 8. Stop-Condition Evidence Format

When a hard stop fires, write `research/loop-<N>/BLOCKER-tdd-<K>.md`:

```markdown
# BLOCKER — <domain> loop <N> TDD iter <K>

- Condition fired: <stop_if key>
- Detected at: <ISO timestamp>
- Evidence: <path to log / assertion / diff>
- Recommended next action: <one sentence>
- Human required: <true|false>
```

Then call `vmc_report_progress` with `phase="blocked"` and link to this file in `evidence`.

## 9. Related Documents

- Parent plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](../../plans/vmc-autoresearch-platform.plan.md) (Phase 2)
- Upstream skill: [`vmc-autoresearch-core`](../vmc-autoresearch-core/SKILL.md)
- Verifier: [`autonomous-verifier`](../autonomous-verifier/SKILL.md)
- Reliability rule: [`reliability-verification`](../../rules/reliability-verification.mdc)
- Testing rule: [`agent-testing-contract`](../../rules/agent-testing-contract.mdc)
- Local CI rule: [`local-ci-before-push`](../../rules/local-ci-before-push.mdc)
- Surgical changes rule: [`surgical-changes`](../../rules/surgical-changes.mdc)

## 10. AutoPilot Hybrid Evidence Bridge

When this TDD loop is invoked from `vmc-autopilot-oneshot` Hybrid mode, keep the TDD iteration report as the detailed source artifact and mirror gate-level results into the active AutoPilot evidence bundle:

- RED/GREEN/refactor commands and exit codes: `artifacts/autopilot/<bundle>/commands.log`
- null-hypothesis `z_score` and verdict: `artifacts/autopilot/<bundle>/metrics.json`
- residual TDD risks and rollback notes: `artifacts/autopilot/<bundle>/risks.md`
- human summary and delta interpretation: `artifacts/autopilot/<bundle>/REPORT.md`

The shared phase-exit gate is `run_phase_exit_gate(context)` from [`../vmc-autopilot-oneshot/reference.md`](../vmc-autopilot-oneshot/reference.md); this skill does not define a separate phase-exit schema.
