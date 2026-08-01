# Pilot Scenarios

Five scenarios exercise the parts of [SKILL.md](../SKILL.md) and
[review-gate.md](../review-gate.md) that are easy to describe and easy to get
wrong. Each has a checked-in artifact under [pilots/](pilots/) and an expected
outcome asserted by [scripts/pilots-run.sh](../scripts/pilots-run.sh).

```bash
bash .cursor/skills/guided-project-discovery/scripts/pilots-run.sh
```

Three fixtures must validate and **two must be rejected**. The negative cases are
the load-bearing ones: a validator that has only ever seen well-formed input is
indistinguishable from one that passes everything.

| # | Scenario | Artifact | Expected |
|---|---|---|---|
| 1 | Sufficient context short-circuits the interview | `01-sufficient-context.DISCOVERY.md` | valid |
| 2 | Interrupted session resumes from `lens_cursor` | `02-interrupted-resume.DISCOVERY.md` | valid |
| 3 | Conflicting required approvers, resolved by a human | `03-conflicting-reviewers.round-1.md` | valid |
| 4 | Plan approval claiming execution authority | `04-execution-not-authorized.round-1.md` | **rejected** |
| 5 | Approvals stale by candidate digest and by authority revision | `05-stale-approval.round-3.md` | **rejected** |

## 1 — Sufficient context

The requester supplied most of the context and the repository answered the rest.
Stage 0 pre-fills two lenses from `docs/setup.md` and `.devcontainer/`, only two
lenses are actually asked, and the interview offers an early exit after the
success-evidence lens.

Demonstrates that discovery scales down. The failure this guards against is an
agent that runs the full lens bank because the bank exists, asking questions whose
answers are already in the repository.

## 2 — Interrupted resume

The session stops after L3 with five blocking lenses outstanding. The ledger holds
`lens_cursor: L4` and `status: interviewing`, so a later session resumes at
Constraints without re-asking L1 to L3.

Demonstrates that interview state lives in the ledger rather than the
conversation. The validator enforces the invariant that makes this work —
`lens_cursor` must name a lens that exists in the table.

Note that the ledger is legitimately incomplete here. Blocking lenses may sit
`open` while `status: interviewing`; the same ledger at `ready-for-review` fails.

## 3 — Conflicting required approvers

Two required approvers file blocking feedback on the **same field**, and their
positions are incompatible: security requires EU-only residency, cost objects that
EU-only doubles storage and strands a US-only analytics cluster.

The agent does not pick a side, split the difference, or defer to seniority. It
presents both positions with consequences and stops. The human accepts the
residency constraint, then dispositions the cost objection by changing *what
crosses the boundary* — analytics consumes an in-region aggregated extract — and
both dispositions carry Decision Deltas. Re-review is triggered for both
authorities because both cover the redlined field.

Demonstrates that disagreement between humans is escalated, not averaged, and
that the resulting change is traceable to the feedback that caused it.

## 4 — Plan approval does not authorize execution

A well-formed plan-mode round with two satisfied required approvers, which then
declares itself execution authority. The validator rejects it on both counts: the
gate result claims execution is authorized, and one approval swaps its mandatory
scope limit for `authorizes-execution`.

```text
FAIL: Execution Authorized: yes — a review round never authorizes execution (review-gate.md section 10)
FAIL: A2 must carry Scope Limit: does-not-authorize-execution
FAIL: ## Gate Result Execution Authorized must be no, got yes
```

Demonstrates the hard prohibition mechanically. This is the failure mode the rule
exists for, and it is quiet: both reviewers approved a *document*, neither
authorized a deployment, and nothing in the round's approval count reveals the
difference.

## 5 — Stale approvals

Two ways an approval goes stale, in one round:

- `A1` approves the round-2 candidate digest. The candidate was redlined since, so
  dana approved text that is no longer being handed off.
- `A2` was given under `AUTH-SEC@3`, but the authority is now at revision 4. The
  standard changed after the approval, so it was given against rules that no
  longer hold.

Both are caught, and because neither approval counts, the round's `status:
approved` is contradicted as well:

```text
FAIL: A1 is stale — it approves sha256:9e51186… but this round is sha256:aee9e4bb…
FAIL: A2 is stale — approved under AUTH-SEC@3 but AUTH-SEC is now at revision 4
FAIL: status is approved but required approver priya@example.com has no non-stale approval in this round
FAIL: status is approved but required approver dana@example.com has no non-stale approval in this round
```

Demonstrates that approval is bound to the exact candidate *and* the exact
authority revisions. Neither form of staleness is visible to someone skimming the
round — the approvals look complete, the count reads 2/2 — which is why the check
is mechanical rather than a review instruction.
