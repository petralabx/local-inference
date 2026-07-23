# Project Hardener — Reference

Detailed contracts loaded from [SKILL.md](SKILL.md): taxonomy, adversarial role
formats, baseline/regression mechanics, stop evidence, and manual hook wiring.

## 1. Triage Taxonomy

Classify each finding once and keep labels stable across loops.

| Label | Definition | Typical signal | Default first move |
|---|---|---|---|
| `bug` | implementation defect violating expected behavior | failing unit/integration test, runtime error | reproduce, isolate root cause, add regression test |
| `UI-UX wiring` | UI behavior is present but incorrectly wired to state/data/actions | controls render but act on wrong state, stale view updates | add interaction test, verify data flow and event wiring |
| `missing-wiring` | required route/state/handler/prop path does not exist | button does nothing, endpoint not connected, callback missing | add absent wiring and integration test |
| `gap` | approved spec requirement is not implemented yet | spec criterion red with no defect in existing path | implement minimal requirement with acceptance test |
| `regression` | behavior that was previously green now fails after a hardening change | baseline delta introduces new failures | rollback/fix immediately before continuing |

Triage notes should include: finding id, label, severity, affected paths, and proof.

## 2. Role Contracts (Fixer and Auditor)

Lineage: this adversarial split generalizes patterns inspired by
`.claude/agents/fixer.md` and `.claude/agents/auditor.md`, but does not depend on
them at runtime.

### 2.1 Fixer contract

The fixer executes one finding at a time:

1. Reproduce defect and capture evidence.
2. Write a regression test that fails pre-fix.
3. Implement the smallest diff that flips only this finding.
4. Re-run targeted regression test to passing.
5. Produce side-effect scan and verification output.

Hard prohibitions:

- No multi-defect bundles.
- No drive-by refactors.
- No weakening/removing tests to force green.
- No silent enhancement outside approved spec.

Fixer verdict format:

```text
FINDING: <id> (<label>, <severity>)
STATUS: FIXED | BLOCKED | ESCALATE
ROOT_CAUSE: <mechanism, not symptom>
TEST: <path> + fail-then-pass evidence
DIFF: <minimal change summary>
SIDE_EFFECT_SCAN: <shared surfaces reviewed>
VERIFICATION: <commands + exit codes>
```

### 2.2 Auditor contract (read-only)

The auditor independently verifies fixer claims:

1. Confirms fail-then-pass test behavior.
2. Validates test targets root cause.
3. Reviews side effects in adjacent shared paths.
4. Rejects scope creep or unrelated edits.
5. Confirms no hidden regressions in rerun results.

Hard prohibitions:

- No file edits.
- No approval by plausibility without execution evidence.

Auditor verdict format:

```text
FINDING: <id>
VERDICT: CONFIRMED | REJECTED
TEST_VALIDITY: <root-cause coverage + fail/pass proof>
SIDE_EFFECTS: <paths checked + outcomes>
SCOPE: CLEAN | VIOLATIONS(<paths>)
REGRESSION_STATUS: NONE | PRESENT(<details>)
REQUIRED_NEXT_ACTION: <if rejected>
```

## 3. Baseline and Regression Mechanism

## 3.1 Snapshot contract

`scripts/baseline-snapshot.sh` creates a key-value manifest from canonical quality
commands. It records:

- command strings used for test/e2e/lint/typecheck
- pass/fail booleans
- total failure count
- timestamp and cwd for traceability

Use once before hardening begins.

## 3.2 Current-run contract

After each accepted fix, capture a current manifest with the same keys.

## 3.3 Diff contract

`scripts/regression-diff.sh` compares baseline and current manifests:

- Regression if baseline had pass and current has fail on any key.
- Regression if current failure count exceeds baseline failure count.
- Clean if no pass->fail transitions and no higher failure total.

Exit codes:

- `0`: no regressions
- `2`: regression detected
- `64`: usage error / malformed input

## 4. Stop-Condition Evidence Format

On hard stop, report with this template:

```text
STOP_REASON: <max_loops_reached|no_progress_or_oscillation|unfixable_regression|evidence_missing|scope_guard_violation>
LOOP_COUNT: <n>/<max>
OPEN_FINDINGS: <count and ids>
FAILED_GATES: <commands + exit codes>
BASELINE_DIFF: <regressions summary>
EVIDENCE_PATHS:
  - <path/to/log-or-report>
NEXT_ACTION:
  - <concrete re-entry step>
```

No stop may be reported without command evidence.

## 5. Edge-3 Escalation Contract

If a high-severity finding cannot be resolved within the approved spec:

1. Freeze new enhancement edits.
2. Record why spec constraints block safe resolution.
3. Route escalation:
   - re-spec required -> `project-orchestrator`
   - re-research required -> `project-researcher`
4. Include artifacts: failing evidence, attempted fixes, regression diff, and proposed
   spec/research question.

This closes the loop instead of introducing unsanctioned scope creep.

## 6. Edge-2 Intake Checklist

Before first hardening loop, verify orchestrator handoff artifacts:

1. integration branch is identified
2. approved `SPEC.md` is present
3. phase evidence bundle exists (`patch.diff`, `NOTES.md`, `commands.log`)
4. integration verification evidence exists
5. hardening target + loop budget are explicit

Missing intake artifacts are a blocker, not an invitation to guess.

## 7. Optional Hook Wiring (manual opt-in)

The hook helper at `.cursor/hooks/verifier-rerun.sh` can be wired manually to
`subagentStop` for reminder-style reruns.

This skill intentionally does not edit `.cursor/hooks.json`. Keep hook setup local
and explicit.

## 8. See Also

- [orchestration-kernel](../orchestration-kernel/SKILL.md) — shared spine contract
- [project-orchestrator](../project-orchestrator/SKILL.md) — Edge-2 handoff source
- [project-researcher](../project-researcher/SKILL.md) — Edge-3 re-research target
