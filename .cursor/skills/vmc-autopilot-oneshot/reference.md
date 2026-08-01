# VMC AutoPilot OneShot Reference

## Phase Map

- `A`: callback preflight, auth/reachability checks, baseline metrics
- `B`: dispatch metadata parity and callback contract completeness
- `C`: callback/poll reconciliation hardening and chat failure visibility
- `D`: Today/System Pulse reliability and pillar signal alignment
- `E`: self-healing + self-improving loop after stable SLO window

## Required Inputs

At invocation time, collect:

1. `phase` (A-E)
2. `goal` (one sentence)
3. optional `branch` (auto-derived if omitted)
4. `mode` (`waterfall` unless the trigger explicitly says `Hybrid`)
5. ownership globs or phase brief that declares writable scope

## Required Outputs

Before declaring completion, provide:

1. Verification commands and pass/fail outcomes
2. VMC lifecycle evidence
3. Browser snapshot evidence for UI-relevant changes
4. Reliability metric before/after deltas
5. Residual risks and rollback notes
6. Hybrid evidence bundle when the Hybrid alias is used

## Baseline Source

Hybrid runs compare against the frozen baseline at `artifacts/autopilot/<yyyy-mm-dd>-baseline/metrics.json`.

Baseline bundles must include `REPORT.md`, `artifacts.json`, and `metrics.json`. Do not create loose files directly under `artifacts/`.

If fewer than three historical phases exist, freeze the available evidence and mark unavailable fields as `null` with `sample_gap` evidence. Do not synthesize missing baselines.

## Phase-Exit Metrics

`run_phase_exit_gate(context)` must compute every metric below. A metric can be `not_applicable` only when the table allows it.

| Metric | Formula | Target | Gate check |
|---|---|---|---|
| `scope_drift_commit_rate` | `commits_with_out_of_scope_edits / phase_commits` | `0` | `detect_scope_drift` |
| `replan_rate` | `replans_triggered / phases_attempted` | informational; alert if `> 2` per phase | `check_replan_limits` |
| `plan_hash_repeat_count` | consecutive replans that produce the same `plan_hash` after the first | `0`; halt on second identical replan | `check_replan_limits` |
| `max_required_evidence_age_seconds` | max age of required evidence files at phase exit | `<= 600` | `detect_evidence_drift` |
| `lane_terminal_state_coverage` | `lanes_with_terminal_state / lanes_spawned` | `1.0` when lanes spawned; otherwise `not_applicable` | `check_parallel_lane_states` |
| `unresolved_cross_lane_conflicts` | overlapping `owns` globs not serialized before merge | `0` | `check_parallel_lane_states` |
| `orchestrator_single_writer_violations` | shared artifact writes by non-orchestrator lanes | `0` | `check_parallel_lane_states` |
| `phase_exit_gate_pass_rate` | `phases_passing_gate_on_first_attempt / phases_attempted` | report baseline first, then no regression in validation harness | `check_quality_metrics` |
| `evidence_bundle_completeness` | `required_files_present / required_files_total` | `1.0` | `check_quality_metrics` |
| `session_resume_success_rate` | `successful_resumes_without_human_rehydration / resume_trials` | `>= 0.9` in validation harness | `detect_context_drift` |
| `model_drift_z_score` | `(candidate_metric - baseline_metric) / variance_unit` | `>= 1.0` only when numeric eval/null arm exists; otherwise `not_applicable` | `detect_model_drift` |

## Drift Detector Contracts

Each detector is a single function invoked by `run_phase_exit_gate(context)`. Missing detectors fail the gate.

| Class | Function | Detects | Replan trigger |
|---|---|---|---|
| Scope drift | `detect_scope_drift(ownership_manifest, git_diff, lane_manifest)` | Edits outside declared ownership, or writes to shared paths by non-orchestrator lanes | Revert offending edits, then scoped replan |
| Plan drift | `detect_plan_drift(active_plan, ledger, command_log, edit_trace)` | Shell/edit trace diverges from the active plan step | Pause, update plan, append `replan` ledger record |
| Evidence drift | `detect_evidence_drift(evidence_bundle_path, required_files, now, max_age_seconds=600)` | Missing evidence files or stale evidence timestamps | Rerun verification matrix |
| Context drift | `detect_context_drift(ledger_path, branch)` | Latest `gate_entry`/`gate_exit` records cannot reconstruct active state | Halt for rehydration |
| Model drift | `detect_model_drift(metrics, null_hypothesis_control)` | Numeric quality delta drops inside noise (`z_score < 1.0`) | Swap executor tier per composed orchestrator rules |

Detector return shape:

```json
{
  "detector": "detect_scope_drift",
  "status": "pass|fail|not_applicable",
  "metric_key": "scope_drift_commit_rate",
  "metric_value": 0,
  "evidence_ref": "artifacts/autopilot/<bundle>/metrics.json",
  "decision": "continue|replan|halt"
}
```

## Phase Gate Algorithm

```text
run_phase_exit_gate(context):
  load ledger and active plan
  load evidence bundle
  load ownership and lane manifests
  run detect_scope_drift
  run detect_plan_drift
  run detect_evidence_drift
  run detect_context_drift
  run detect_model_drift
  run check_replan_limits
  run check_parallel_lane_states
  run check_quality_metrics
  fail if any required detector is missing
  fail if any hard target fails
  fail if evidence_bundle_completeness < 1.0
  append gate_exit only after pass
```

## Decision Ledger Schema

Canonical path: `.cursor/plans/ledger/<branch>/ledger.jsonl`.

The ledger is append-only. Required fields per JSONL entry:

```json
{
  "ts": "ISO-8601 timestamp",
  "phase": "A|B|C|D|E",
  "iteration": 1,
  "event": "gate_entry|plan|exec|verify|replan|gate_exit|escalate",
  "plan_hash": "sha1 of active plan step list",
  "decision": "string",
  "rationale": "string",
  "evidence_ref": "path under artifacts/",
  "metrics": {
    "drift_class": "scope|plan|evidence|context|model|none",
    "z_score": 0.0
  }
}
```

Session resume procedure:

1. Read `.cursor/plans/ledger/<branch>/ledger.jsonl`.
2. Find the latest `gate_entry` for the active phase.
3. Find the latest `gate_exit` for the active phase.
4. Reconstruct phase, iteration, active `plan_hash`, evidence bundle, and last terminal decision.
5. If records are absent, malformed, or contradictory, enter rehydration mode and halt before edits.

## Evidence Bundle Schema

Canonical path: `artifacts/autopilot/<yyyy-mm-dd>-<phase-lower>-<slug>/`.

Required files:

- `REPORT.md`: human summary, metric deltas vs baseline, phase result
- `artifacts.json`: bundle index listing each evidence file and purpose
- `commands.log`: every shell command, cwd, exit code, and timestamp
- `mcp-evidence.json`: MCP tool I/O evidence with schema version
- `metrics.json`: numeric gate results keyed to the metrics above
- `ledger-snapshot.jsonl`: copied ledger records relevant to this phase
- `risks.md`: residual risks, rollback notes, and blockers

`artifacts.json` required shape:

```json
{
  "schema_version": "autopilot.artifacts.v1",
  "bundle": "artifacts/autopilot/<yyyy-mm-dd>-<phase-lower>-<slug>",
  "files": [
    {
      "path": "REPORT.md",
      "purpose": "human summary and metric deltas"
    }
  ]
}
```

`metrics.json` required shape:

```json
{
  "schema_version": "autopilot.metrics.v1",
  "phase": "A",
  "mode": "hybrid",
  "baseline_ref": "artifacts/autopilot/baseline-<date>/metrics.json",
  "gate_result": "pass|fail|blocked",
  "metrics": {
    "scope_drift_commit_rate": 0,
    "replan_rate": 0,
    "plan_hash_repeat_count": 0,
    "max_required_evidence_age_seconds": 0,
    "lane_terminal_state_coverage": 1,
    "unresolved_cross_lane_conflicts": 0,
    "orchestrator_single_writer_violations": 0,
    "phase_exit_gate_pass_rate": 1,
    "evidence_bundle_completeness": 1,
    "session_resume_success_rate": 1,
    "model_drift_z_score": "not_applicable"
  },
  "detectors": []
}
```

`mcp-evidence.json` required shape:

```json
{
  "schema_version": "autopilot.mcp-evidence.v1",
  "calls": [
    {
      "tool": "vmc_get_context",
      "descriptor_read": true,
      "ts": "ISO-8601 timestamp",
      "request_ref": "redacted or path",
      "response_ref": "redacted or path",
      "outcome": "pass|fail|blocked"
    }
  ]
}
```

## Skill-Local Validators

The Hybrid phase-exit gate must run these helpers from `scripts/`:

1. `validate-evidence-bundle.py <bundle>` checks bundle naming, required files, required JSON keys, and evidence freshness.
2. `validate-ledger.py <ledger.jsonl>` checks JSONL parseability, required ledger fields, event ordering, and resume reconstruction fields.
3. `validate-detectors.py <metrics.json>` checks detector result shape and ensures failed detectors map to `replan` or `halt`.

All helpers must fail closed for malformed input. A helper failure blocks `gate_exit`.

## Validation Harness

Run `N=5` archived dry-run trials across at least two phase types before promotion from canary. Include at least one seeded failure for each drift class.

For each trial:

1. Start from a frozen archived task or artifact.
2. Create a ledger with `gate_entry`.
3. Reconstruct prior state without human rehydration.
4. Execute detector checks against the archived diff/evidence.
5. Emit per-trial `metrics.json`.
6. Publish aggregate report at `artifacts/autopilot/eval-<date>/REPORT.md`.

Promotion requires no regression against frozen baseline on every available metric and measurable improvement in at least one drift, orchestration, and quality metric. If baseline data is unavailable, promotion remains blocked until enough real hybrid trials exist.

## Guardrails

- Never execute MCP calls before reading tool descriptors.
- Never skip staging preflight for DB/external operations.
- Never advance phase without gate evidence from the active contract.
- Never mark done with failing CI, failing detector, stale evidence, or untriaged comments.
- Never create new `.cursor/rules/*.mdc` files for this plan without explicit operator approval.
