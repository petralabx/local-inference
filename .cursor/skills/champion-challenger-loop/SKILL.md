---
name: champion-challenger-loop
description: Bounded self-improving optimization loop for any testable artifact (prompt, policy, config, ranking heuristic, scoring rule). Holds a protected champion plus its gate score, spends a fixed budget proposing one targeted untried challenger per cycle from the latest failure, scores challengers on a cheap tunable working signal, and promotes only on a fresh independent acceptance gate with a minimum margin and no guard regression. Rejects suspiciously easy wins as Goodhart's law and keeps the champion when uncertain. Use when cheap iteration is useful but final acceptance must use fresh evidence the editor never inspected — e.g. "self-improving loop", "champion challenger", "optimize this prompt/config with a holdout gate", "evolve this heuristic safely".
---

# Champion / Challenger Loop

A bounded optimization loop that tests targeted challengers, protects an
independently evaluated champion, and rejects suspiciously easy wins. It improves
a testable artifact (a prompt, policy, config, ranking/scoring rule) when cheap
iteration is useful **but final acceptance must use fresh evidence** you did not
look at while editing.

The whole point is to keep the **tunable working signal** strictly separate from
the **fresh acceptance gate**. Tuning against the gate is how you fool yourself.

## The invariant (read this first)

1. The **champion is default-safe**. Every cycle keeps the champion unless a
   challenger clears the gate by a real margin with no guard regression.
2. **Working signal ≠ gate.** You may tune freely against the working signal. The
   gate uses fresh examples you never inspected while editing, plus the guards.
3. **Reject easy wins.** A suspiciously large/cheap jump is Goodhart's law in
   action (leakage, overfit, a weakened guard). Re-verify or reject.
4. **When uncertain, keep the champion.** Ambiguity resolves to no-promote.

## When to Use

- Improving a prompt, system message, routing policy, config, or any artifact you
  can score automatically and re-score on held-out examples.
- You can afford many cheap working-signal evaluations and a smaller number of
  trustworthy gate evaluations.
- The user says "self-improve / evolve / optimize X with a holdout", "champion
  challenger loop", or "tune this but don't overfit".

## When NOT to Use

- There is no fresh/held-out evidence available — without a gate this loop degrades
  into overfitting the working signal. Build the gate first.
- A single deterministic fix is obviously correct (just make the fix; this loop is
  for search under uncertainty).
- Acceptance is inherently human/qualitative with no scoreable gate — use a review
  loop (`adversarial-review-loop`) instead.

## State you must hold

Keep these in memory (and persisted to the evidence bundle) for the whole run:

```yaml
champion:        { genome: <artifact>, gate_score: <number>, working_score: <number> }
budget:          <N>                 # cycles remaining; fixed at start
attempt_log:     [ { genome, working_score, gate_score|null, verdict, reason } ]
working_signal:  <cheap scorer you MAY tune against>
gate:            <fresh examples + scorer, NEVER inspected during editing>
guards:          [ <guard check> ... ]      # the [safety] set
minimum_margin:  <Δ the gate score must beat the champion by>
```

## Parameters to define BEFORE starting

Do not start the loop until all of these are pinned (write them into the bundle):

- `[N]` — the budget (number of cycles).
- `[minimum margin]` — how much the gate score must exceed the champion's.
- **working signal** — the cheap measure you may tune against.
- **gate examples** — fresh, held-out, never used for editing or proposing.
- `[safety]` — the guard checks that must not regress on any promotion.

Treat reusing gate examples for editing, or silently weakening a guard after a
failed challenger, as a contract violation that invalidates the run.

## The loop

```text
initialize champion, working_signal, gate, guards, minimum_margin, budget=N, log=[]
while budget > 0:
    budget -= 1
    failure   = latest failure / weakness in the log (or the seed task on cycle 1)
    challenger = propose ONE targeted change to the champion that addresses `failure`
    if challenger already in log:        # never re-try a tried genome
        continue
    working = score(challenger) on the working signal      # cheap, tunable
    if working not clearly better than champion.working:
        log(challenger, working, gate=null, verdict="reject:working", ...) ; continue
    freeze(challenger)                                      # stop editing it now
    gate_score, guard_results = evaluate(challenger) on FRESH gate examples + guards
    if gate_score > champion.gate_score + minimum_margin AND no guard regressed:
        if win looks suspiciously easy:                     # Goodhart check
            re-verify on a second fresh slice; if it doesn't hold -> reject
        champion = challenger                               # promote
        verdict = "accept"
    else:
        verdict = "reject:gate"                             # keep champion
    log(challenger, working, gate_score, verdict, reason)
return champion
```

Return the champion when the budget hits zero. The champion at the end is the
only output you ship.

## Working signal vs. gate (the anti-Goodhart core)

| | Working signal | Acceptance gate |
|---|---|---|
| Purpose | guide the search | decide promotion |
| May be tuned against? | yes | **never** |
| Examples | cheap, reusable, may overlap edits | fresh, held-out, unseen while editing |
| Cost | cheap (run often) | trustworthy (run on freeze) |
| Failure if conflated | silent overfitting | — |

If the working signal and gate ever start agreeing perfectly, suspect leakage —
the gate has been contaminated and must be re-cut from unseen data.

## Per-stack backends (delegate, do not reinvent)

This skill is the **universal contract**. The concrete champion store, working
signal, gate, and guards already exist per repo — reference them, do not rebuild:

| Stack | Gate / held-out | Guards | Engine to delegate to |
|---|---|---|---|
| VMC (agentic-swarm) | Postgres holdout eval set | pillar checks, null-hypothesis variance | `vmc-autoresearch-core`, `parallel-multiagent-orchestrator` |
| Trading Lab | frozen `eval/.../baseline.json`, never-read holdout window | golden-verify, leakage-audit | trading `/loop` + `register-experiment` |
| Generic repo | a fresh eval split + harness command | repo test/lint/security gates | a project `eval/` harness |

Repo-specific commands, score formulas, and guard wiring live in
[reference.md](reference.md) — keep `SKILL.md` portable.

## Hard-stop conditions

Halt and emit a hard-stop payload (per `orchestration-kernel` §5) on any of:

```yaml
stop_if:
  no_gate_defined: true                 # cannot accept without fresh evidence
  gate_examples_reused_for_editing: true
  guard_silently_weakened: true
  working_and_gate_perfectly_correlated: true   # suspected leakage
```

Note: budget exhaustion is **not** a hard stop — it is the loop's normal
termination (return the champion). An unchanged champion is a valid, honest
outcome (see the Completion contract), not an error to escalate.

Hard-stop shape:

```yaml
stop_reason: <code from stop_if>
loop: champion-challenger
attempt: <cycle index>
failed_checks: [ { command: <exact>, exit_code: <n> } ]
evidence_paths: [ <bundle path> ]
next_action: <re-cut gate / restore guard / escalate to human>
```

## Completion contract

Do not report the loop done until all are true:

- The returned champion's `gate_score` is recorded with the exact gate command and
  the held-out slice identifier.
- Every cycle has an `attempt_log` entry (accepted and rejected), with the reason.
- No promotion relied on reused gate examples or a weakened guard.
- Any "easy win" promotion was re-verified on a second fresh slice.
- If the budget exhausted with no improvement, say so plainly — an unchanged
  champion is a valid, honest outcome, not a failure to hide.

## Additional resources

- Repo-specific gates, guards, score formulas, worked example: [reference.md](reference.md)
- Shared contracts (model roles, scope-lock, evidence bundle, hard-stop): [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Related loops: [vmc-autoresearch-core](../vmc-autoresearch-core/SKILL.md), [parallel-multiagent-orchestrator](../parallel-multiagent-orchestrator/SKILL.md), [reliable-tdd-loop](../reliable-tdd-loop/SKILL.md)
- Trading variant: [register-experiment](../../../.claude/skills/register-experiment/SKILL.md)
