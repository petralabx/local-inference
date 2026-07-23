---
name: reliable-tdd-loop
description: Enforces failing-test-first discipline scoped to a single domain's contract test file (e.g. todos-contracts, chat-contracts, swarm-contracts, second-brain-contracts). Runs red-green-refactor grind loops via narrow .cursor/hooks.json triggers (beforeShellExecution on `npm test -- <domain>-contracts` only, subagentStop auto-rerun). Includes null-hypothesis control arm (re-run unchanged baseline each loop, record variance) and Tier-1 vs Tier-2 gating. Use inside autoresearch/<domain> loops 2-5, during any reliability bug fix that needs a contract test, or whenever a new failing test must precede implementation.
---

# Reliable TDD Loop

Use this skill to run a disciplined failing-test-first grind loop scoped to a **single domain contract file**. The skill composes with `autonomous-verifier` and `vmc-autoresearch-core`; it does not replace them. Its core discipline is:

1. Write the failing test first, confirm it fails for the right reason.
2. Implement the smallest change that flips the test green.
3. Refactor without changing behavior; re-run the contract file only.
4. Re-run the **null-hypothesis control arm** (unchanged baseline) to confirm the delta is real, not noise.
5. Run Tier-2 (full validate + cross-domain suites) before declaring done.

Canonical plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](../../plans/vmc-autoresearch-platform.plan.md) (Phase 2).

## When to Use

- Inside `autoresearch/<domain>` loops 2-5 (per `vmc-autoresearch-core`).
- Bug fixes that need a new contract invariant before implementation.
- Any change to reliability-critical behavior where a regression must be provable.
- When the user says "run the TDD loop", "red-green-refactor for <domain>", or "drive this with a failing test first".

## When NOT to Use

- Pure documentation edits, dependency bumps, or config-only changes with no behavioral contract.
- Emergency production hotfixes where the fix must ship before a test can be written (write the contract test immediately after, per `tasks/lessons.md` policy).
- Cross-domain refactors that touch >1 `<domain>-contracts.test.ts` — those belong in `cross-domain/*.test.ts` and a different workflow.
- Feature branches outside an `autoresearch/<domain>` branch **unless** the change targets an existing `<domain>-contracts` file.

## Scope Rule (critical difference from generic TDD)

This loop operates on **per-domain contract files**, not the catch-all `reliability-contracts.test.ts`:

```
apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts
apps/vmc-web/src/lib/vmc/__tests__/routes/chat-contracts.test.ts
apps/vmc-web/src/lib/vmc/__tests__/routes/swarm-contracts.test.ts
apps/vmc-web/src/lib/vmc/__tests__/routes/second-brain-contracts.test.ts
```

Adding a test to the catch-all file is a **scope violation** and the skill halts. This forces domain isolation mechanically.

## Quick-Start Checklist

Copy and keep updated while running a TDD loop:

```text
Reliable TDD Loop Progress — domain=<DOMAIN>, iteration=<K>
- [ ] 1) Confirm target file is <domain>-contracts.test.ts (not generic reliability-contracts)
- [ ] 2) Write failing test; run `npm test -- <domain>-contracts`; confirm RED for the right reason
- [ ] 3) Record failure evidence (stack, assertion) in research/loop-<N>/tdd-<K>.md
- [ ] 4) Implement minimal change scoped to eval/ownership.json .owns globs
- [ ] 5) Re-run `npm test -- <domain>-contracts`; confirm GREEN
- [ ] 6) Run null-hypothesis control arm (re-run unchanged baseline, record variance)
- [ ] 7) Refactor without changing behavior; re-run contract file; still GREEN
- [ ] 8) Tier-2 gate: `bash scripts/validate.sh` + all `<other>-contracts` + cross-domain suite
- [ ] 9) Update research/loop-<N>/tdd-<K>.md with deltas (red->green commit SHAs, null variance)
- [ ] 10) `vmc_report_progress` at each GREEN transition; `vmc_complete_task` only after Tier-2
```

## Failing-Test-First Contract

A test is **not valid** for the grind loop unless it satisfies all of these:

1. It lives in exactly one `<domain>-contracts.test.ts` file.
2. On first run (pre-implementation) it **fails** with an assertion matching the documented hypothesis (not an import error, not a syntax error, not a typo).
3. Its failure message encodes the contract (what's expected vs observed).
4. It does not depend on wall-clock flakiness; use fake timers / injected clocks.
5. It does not call external services directly; use the domain's seam (mock / fixture / in-memory adapter).
6. It would pass against a real-but-correct implementation, not just the current stub.

If any rule is violated, the `beforeShellExecution` hook flags a warning (`failClosed: false`, advisory only — the hook is narrow by design).

## Tier-1 vs Tier-2 Gating

| Tier | Command | When to run |
|---|---|---|
| Tier-1 (fast, inner loop) | `npm test -- <domain>-contracts` | Every red->green, every refactor step |
| Tier-2 (slow, outer gate) | `bash scripts/validate.sh` + `npm test -- .*-contracts` + `npm test -- cross-domain` | Before declaring the TDD loop complete; before `vmc_complete_task` |

Tier-1 green is **necessary but not sufficient**. Tier-2 green is the promotion gate.

## Null-Hypothesis Control Arm (required every iteration)

For every red->green transition the loop **must** re-run the unchanged baseline under the same harness and record variance in `research/loop-<N>/tdd-<K>.md`:

```text
## Null-hypothesis control arm
- baseline_commit: <SHA before this iteration's change>
- rerun_metric:    <same pillar as the candidate>
- delta_vs_baseline_frozen_at_loop_1: <signed units>
- variance_unit: eval/baseline.json.null_hypothesis_variance[pillar]
- z_score = delta / variance_unit

Accept the change iff |z_score| >= 1.0 for the target pillar.
Below 1.0 => improvement is inside noise; treat as null result; do NOT merge.
```

This is the only guardrail against "I changed something and the test passes — therefore it works". Variance units ground the claim.

## Grind-Loop Integration with TodoWrite

Each iteration of the loop creates three TodoWrite items in order (only one `in_progress` at a time):

1. `tdd-<K>-red` — write the failing test; status transitions to `completed` only after RED is reproduced on a clean checkout.
2. `tdd-<K>-green` — minimal implementation; completed only after `npm test -- <domain>-contracts` returns 0 on a clean terminal.
3. `tdd-<K>-refactor` — zero-behavior-change cleanup; completed only after Tier-1 still green and Tier-2 gate passes.

No iteration advances until all three are `completed`. The `subagentStop` hook enforces this by rerunning the verifier if any iteration is left dangling.

## Hooks Integration

The project hooks live at `.cursor/hooks.json` and `.cursor/hooks/*.sh`. This skill installs exactly two narrow hooks:

| Event | Matcher | Script | Purpose | failClosed |
|---|---|---|---|---|
| `beforeShellExecution` | `npm test -- .*-contracts` | `.cursor/hooks/tdd-gate.sh` | Advisory: warn if target file is generic `reliability-contracts.test.ts`; block if obvious scope violation | `false` |
| `subagentStop` | *(unfiltered; subagent-side)* | `.cursor/hooks/verifier-rerun.sh` | Auto-rerun Tier-1 when a TDD subagent stops mid-loop (detected via `research/loop-*/tdd-*.md` markers) | `false` (hook reads markers; no markers => exit 0) |

Exclusions (deliberate):

- No generic `beforeMCPExecution` schema-read hook — too broad, slows every MCP call; `vmc-autoresearch-core` and `autonomous-verifier` already enforce schema-first contract.
- No `afterFileEdit` auto-formatter — out of scope; this skill is about test discipline, not formatting.
- No `preToolUse` catch-all — would conflict with unrelated skills.

Full hook script contents + JSON schema: [reference.md §3 and §4](reference.md).

## Completion Contract

Do not mark a TDD loop iteration done until all are true:

- Tier-1 green with command evidence pasted in `research/loop-<N>/tdd-<K>.md`.
- Tier-2 green (validate.sh + all `<domain>-contracts` suites + cross-domain) with exit codes recorded.
- Null-hypothesis control arm executed; `z_score >= 1.0` documented for the target pillar.
- Scope-lock verified: `git diff --name-only <base>..HEAD` contains zero files outside `eval/ownership.json.owns`.
- `vmc_report_progress` called for the iteration; `vmc_complete_task` only after final Tier-2.
- `tasks/lessons.md` updated if a test had to be rewritten mid-loop (signals tagging error) or if the null arm invalidated a seemingly-green change.

## Hard Stop Conditions

Any one halts the loop and triggers `research/loop-<N>/BLOCKER-tdd-<K>.md`:

```yaml
stop_if:
  generic_reliability_contracts_touched: true   # scope violation
  red_test_failed_for_wrong_reason: true        # import error, not assertion
  null_arm_variance_exceeds_delta: true         # change is noise
  tier_2_fails_after_tier_1_green: true         # hidden cross-domain coupling
  iteration_count: ">= 5"                       # ceiling; escalate to human review
  scope_lock_violation: true                    # patch outside ownership.json.owns
```

## Additional Resources

- Full hook script contents, JSON schema, gate commands, null-arm math: [reference.md](reference.md)
- Worked transcripts (todos red-green-refactor x2, stop-condition fire, Tier-2 catch): [examples.md](examples.md)
- Parent plan: [`.cursor/plans/vmc-autoresearch-platform.plan.md`](../../plans/vmc-autoresearch-platform.plan.md) (Phase 2)
- Related skills: [vmc-autoresearch-core](../vmc-autoresearch-core/SKILL.md), [autonomous-verifier](../autonomous-verifier/SKILL.md), [vmc-autopilot-oneshot](../vmc-autopilot-oneshot/SKILL.md)
- Rules: [reliability-verification](../../rules/reliability-verification.mdc), [agent-testing-contract](../../rules/agent-testing-contract.mdc), [local-ci-before-push](../../rules/local-ci-before-push.mdc), [surgical-changes](../../rules/surgical-changes.mdc)
