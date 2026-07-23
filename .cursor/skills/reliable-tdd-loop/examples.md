# Reliable TDD Loop — Worked Examples

Concrete transcripts. Start here after [SKILL.md](SKILL.md) and [reference.md](reference.md).

## Example A: To-Dos Loop 2 — TDD iteration 1 (read-after-write race)

**Context:** inside `~/agentic-swarm-autoresearch-todos/` on branch `autoresearch/todos/loop-02/hyp-03`. Baseline frozen at Loop 1. Hypothesis H3 (tag: `moderate`): roadmap parity drift caused by eventual-consistency race between portal write and VMC `checkout_task`; add read-after-write verification.

### 1) Plan the iteration in TodoWrite

```json
[
  { "id": "tdd-01-red",      "content": "TDD iter 01 RED: failing todos-contracts test asserting read-after-write parity within 200ms",          "status": "in_progress" },
  { "id": "tdd-01-green",    "content": "TDD iter 01 GREEN: implement verify-after-write in portal write path; npm test -- todos-contracts 0",   "status": "pending" },
  { "id": "tdd-01-refactor", "content": "TDD iter 01 REFACTOR: extract verifier into portal/src/lib/todos/read-after-write.ts; Tier-1 green",    "status": "pending" }
]
```

### 2) RED — write the failing test

Target file (must be this exact file, not `reliability-contracts.test.ts`):
`apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts`

```ts
describe("todos write -> roadmap parity", () => {
  it("reflects a portal write in vmc_get_roadmap within 200ms", async () => {
    const id = await portalTodos.create({ title: "t-raw-1" });
    const seen = await waitForRoadmap(id, { timeoutMs: 200 });
    expect(seen.todoId).toBe(id);
  });
});
```

Run Tier-1. The `beforeShellExecution` hook fires:

```text
[hook tdd-gate.sh] command matched `npm test -- .*-contracts`; target=todos-contracts; ownership.json present; permission=allow
```

```bash
$ npm test -- todos-contracts
FAIL  apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts
  ● todos write -> roadmap parity › reflects a portal write in vmc_get_roadmap within 200ms
    Timeout exceeded 200ms waiting for roadmap row todoId=t-raw-1
    expect(received).toBe(expected)
$ echo $?
1
```

Failure is a legitimate assertion (not import / syntax). **RED valid.** Commit:

```bash
git add apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts
git commit -m "test(todos): failing read-after-write parity contract"
# -> red_commit_sha = 1a2b3c4
```

Write `research/loop-02/tdd-01.md` — fill in the Red block. Mark `tdd-01-red` completed.

### 3) GREEN — minimal implementation

Scope-locked to `eval/ownership.json.owns` (`portal/src/lib/todos/**`, etc.). Implement `verifyAfterWrite(id)` that polls `vmc_get_roadmap` up to 200ms and throws on miss.

```bash
$ npm test -- todos-contracts
PASS  apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts
$ echo $?
0
$ git commit -am "feat(todos): verify-after-write to close roadmap parity race"
# -> green_commit_sha = 5d6e7f8
```

### 4) Null-hypothesis control arm (mandatory)

```bash
# Re-run unchanged baseline harness
git checkout autoresearch/todos                                      # pre-iteration baseline
npx tsx eval/harness.ts --mode=score --candidate=null --out=research/loop-02/scorecard-null-tdd-01.json

# Score candidate
git checkout autoresearch/todos/loop-02/hyp-03
npx tsx eval/harness.ts --mode=score --candidate=tdd-01 --out=research/loop-02/scorecard-tdd-01.json
```

```text
baseline_frozen_metric     = 0.9980   # roadmap_parity_pct p50 from eval/baseline.json
baseline_rerun_metric      = 0.9978
candidate_metric           = 0.9995
variance_unit              = 0.002
delta_candidate_vs_frozen  = +0.0015
delta_rerun_vs_frozen      = -0.0002   # noise estimate well under variance_unit
z_score                    = +0.75
```

`|z_score| < 1.0` — this is a **null result**. The test passes but the pillar-level improvement is inside noise.

Action per skill contract: **do not advance to refactor**. Revisit hypothesis:

- Option A: tighten contract (require parity within 100ms, not 200ms) — stronger test.
- Option B: scale N (run harness with `--n=1000`) to reduce variance_unit before re-scoring.
- Option C: accept as null-result, record in `research/loop-02/REPORT.md`, do not merge.

Documented in `research/loop-02/tdd-01.md` Null block with verdict `null-result`. Do **not** call `vmc_complete_task`.

### 5) Iterate: TDD iteration 2 chooses Option A (tighten to 100ms) and repeats

Re-score; z_score = +1.6. Verdict `accept`. Proceed to refactor and Tier-2.

### 6) REFACTOR

Extract the polling logic into `portal/src/lib/todos/read-after-write.ts`. Tier-1 still green; commit.

### 7) Tier-2 gate

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
bash scripts/validate.sh
for d in todos chat swarm second-brain; do npm test -- "$d-contracts"; done
npm test -- cross-domain
```

All green. Scope-lock audit clean. Call `vmc_report_progress` then `vmc_complete_task` with evidence from `research/loop-02/tdd-02.md`.

## Example B: Scope-violation advisory (deprecated generic file)

User attempts:

```bash
npm test -- reliability-contracts
```

Hook output:

```json
{
  "permission": "ask",
  "user_message": "reliable-tdd-loop advisory: you are running the deprecated catch-all `reliability-contracts` suite. This skill requires a per-domain `<domain>-contracts.test.ts` file (todos-contracts, chat-contracts, swarm-contracts, second-brain-contracts).",
  "agent_message": "Add the new test to a per-domain contract file before proceeding, or confirm this is legacy maintenance and bypass the advisory."
}
```

Cursor surfaces the `ask` prompt. If the user confirms (legacy maintenance), the command proceeds. The skill records the override in `tasks/lessons.md`.

## Example C: `subagentStop` auto-rerun catches a dangling iteration

A `best-of-n-runner` subagent crashed mid-GREEN step. The Green block in `research/loop-02/tdd-01.md` has no `exit_code`.

When the subagent stops, `.cursor/hooks/verifier-rerun.sh` runs:

```json
{
  "followup_message": "Dangling TDD iteration detected at research/loop-02/tdd-01.md (Green block missing exit_code). Re-run `npm test -- todos-contracts`, update the Green block with exit_code + green_commit_sha, then re-run the null-hypothesis control arm before advancing."
}
```

Main agent re-runs Tier-1, fills in the missing fields, and advances. `loop_limit: 2` ensures this can't retrigger forever.

## Example D: Tier-2 catch after Tier-1 green (cross-domain coupling)

Tier-1 `npm test -- todos-contracts` green. Tier-2 run reveals:

```bash
$ npm test -- chat-contracts
FAIL  apps/vmc-web/src/lib/vmc/__tests__/routes/chat-contracts.test.ts
  ● chat creates todo from slash command › schema-valid response
    Expected todoId to be a ULID; received empty string.
$ echo $?
1
```

The read-after-write change altered a response shape consumed by chat. **Hidden coupling.** Do not merge. Two options:

- Option A: keep the fix domain-local by adding a back-compat shim in the todos return shape so chat-contracts passes unchanged.
- Option B: pull the change into a cross-domain PR and add a `cross-domain/*.test.ts` pinning the interface before merging.

Either way, write `research/loop-02/BLOCKER-tdd-02.md` with `tier_2_fails_after_tier_1_green: true`. `vmc_report_progress` with `phase="blocked"`. Do not call `vmc_complete_task`.

## Example E: Null-arm invalidates a seemingly-green change

TDD iter 3 on `chat` domain. Hypothesis (tag: `mechanical`): reorder zod validators to short-circuit cheaply. Tier-1 green, but:

```text
baseline_frozen_metric (schema_valid_response p50) = 1.0000
baseline_rerun_metric                              = 1.0000
candidate_metric                                   = 1.0000
variance_unit                                      = 0.001
z_score                                            = 0.0
```

No measurable improvement. The test still passes, but per skill contract the iteration produces no reliability gain. Mark as null-result in `research/loop-0N/REPORT.md`; the PR is not declined but the iteration does **not** count toward loop-gate advancement. `tasks/lessons.md` gets a one-liner: "zod reorder did not move `schema_valid_response` in harness; do not count as reliability improvement".

## Example F: Failed RED — wrong reason (import error)

Author writes a test but forgets to export `waitForRoadmap`. First run:

```bash
$ npm test -- todos-contracts
FAIL  apps/vmc-web/src/lib/vmc/__tests__/routes/todos-contracts.test.ts
  ● Test suite failed to run
    Cannot find module '@/lib/todos/test-helpers'
```

This is **not a valid RED** (fails on module resolution, not contract assertion). The skill halts the iteration and writes `research/loop-02/BLOCKER-tdd-01.md`:

```markdown
# BLOCKER — todos loop 02 TDD iter 01

- Condition fired: red_test_failed_for_wrong_reason
- Detected at: 2026-04-23T20:14:00Z
- Evidence: import error `Cannot find module '@/lib/todos/test-helpers'`
- Recommended next action: export `waitForRoadmap` from the helper module, re-run, confirm RED failure is the assertion (not import).
- Human required: false
```

Iteration resumes only after a re-run produces an assertion-level failure.

## Trigger Phrase Reference

| Phrase | Action |
|---|---|
| `run the TDD loop for <domain>` | Enter skill, initialize iteration 1 TodoWrite items, open `research/loop-<N>/tdd-01.md` scaffold |
| `red-green-refactor for <domain>` | Same as above |
| `TDD iter <K> for <domain>` | Resume / start iteration K |
| `TDD stop <domain>` | Evaluate hard-stop conditions; write BLOCKER if any fire; report via VMC |
| `TDD tier-2 <domain>` | Run the Tier-2 command block from reference.md §5 |
