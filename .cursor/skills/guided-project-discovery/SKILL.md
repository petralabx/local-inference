---
name: guided-project-discovery
description: Interview a vague project into a decision-ready brief one lens at a time, keep a resumable discovery ledger, then route it to research, plan, or execute mode behind a collaborative review gate that binds reviewer approval to an exact frozen candidate. Use when the user says "help me scope this", "interview me about this project", "I have an idea but haven't thought it through", or hands over an initiative that needs discovery and reviewer sign-off before anything gets built.
---

# Guided Project Discovery

Turn an under-specified initiative into an approved handoff. The skill conducts an
adaptive interview **one lens at a time**, records every answer in a resumable
`DISCOVERY.md` ledger, and then passes the result through a **collaborative review
gate** before any downstream skill is allowed to run.

This skill owns discovery, review, and routing. It does **not** re-implement
research, planning, or build execution — those stay with `project-researcher`,
`project-orchestrator`, and `project-hardener` under the shared contracts in
[orchestration-kernel](../orchestration-kernel/SKILL.md).

## When to Use

- The user has an intent, not a specification, and the gap is wide enough that a
  single question batch will not close it.
- Trigger phrases include "help me scope this", "interview me about this project",
  "I have an idea but haven't thought it through", "walk me through what you need
  to know".
- The output needs sign-off from people other than the requester before work
  starts.
- A previous discovery session was interrupted and needs to resume where it
  stopped.

## When NOT to Use

- The work is already specified and approved — go straight to the spine skill.
- One short batch of clarifying questions would be enough. That is
  [pre-plan-recalibrator](../pre-plan-recalibrator/SKILL.md); this skill is the
  heavier, resumable, multi-stakeholder path.
- The user explicitly asked to skip discovery and start building.
- The question is a bug or a debugging problem, which belongs to
  `root-cause-debugger` or `codebase-investigation`.

## Modes

The mode is chosen by the human at Stage 3 and written into the ledger. It bounds
what the approved handoff is allowed to start.

| Mode | Produces | Hands off to | May write product code |
|---|---|---|---|
| `research` | `RESEARCH.md` brief | `project-researcher` | no |
| `research+plan` | brief and an approved `SPEC.md` | `project-researcher`, then `project-orchestrator` Stages 1-2 | no |
| `research+plan+execute` | brief, spec, and built phases | the full `project-orchestrator` lifecycle | yes, only after the separate execution authorization in Stage 5 |

Selecting `research+plan+execute` at Stage 3 declares an *intent* to execute. It
does not authorize execution. See [Stage 5](#stage-5--handoff).

## Lifecycle

```text
Guided Project Discovery — <slug>
- [ ] Stage 0  Intake: seed the ledger, infer what is already known
- [ ] Stage 1  Adaptive interview, one lens per turn, skip what is answerable
- [ ] Stage 2  Ledger converges: no open blocking lens, assumptions recorded
- [ ] Stage 3  Human picks mode and names review authorities
- [ ] Stage 4  Collaborative review gate: freeze, review, dispose, approve
- [ ] Stage 5  Handoff to the spine skill for the approved mode
```

### Stage 0 — Intake

Create `.discovery/<slug>/DISCOVERY.md` from the ledger schema in
[reference.md](reference.md#1-discovery-ledger-schema). Before asking anything,
read the repository, prior briefs, linked tickets, and the conversation so far,
and pre-fill every lens the evidence already answers. Record each pre-filled
answer with its source so the human can correct it.

An interview that asks what the agent could have read is a failed interview.

### Stage 1 — Adaptive interview

Ask about **one lens per turn**. A lens is a single decision-relevant dimension —
outcome, users, constraints, blast radius, and so on. The full lens bank is in
[reference.md](reference.md#2-lens-bank).

Rules:

1. One lens per turn, with at most three tightly-related questions inside it.
2. Choose the next lens by expected information gain, not by list order. Ask the
   lens whose answer most changes the shape of the work.
3. Skip any lens already answered by evidence, and say what evidence answered it.
4. After each answer, write it to the ledger and advance `lens_cursor` **before**
   asking the next question. The ledger, not the conversation, is the state.
5. Offer the user an early exit whenever the remaining lenses no longer change the
   recommendation. State what would stay assumed.
6. Never batch the whole lens bank into one questionnaire.

Because the ledger is written before each new question, an interrupted session
resumes by reading `lens_cursor` and continuing — no re-asking.

### Stage 2 — Convergence

Discovery converges when every blocking lens is answered or explicitly waived,
open questions are either resolved or recorded as assumptions with an owner, and
non-goals are written down. Then set `status: ready-for-review`.

Validate the ledger before offering it for review:

```bash
bash .cursor/skills/guided-project-discovery/scripts/discovery-validate.sh .discovery/<slug>/DISCOVERY.md
```

### Stage 3 — Mode and authorities

Present the converged ledger and ask the human for two things:

1. **Mode** — one of the three above.
2. **Review authorities** — who owns which fields, and in which role. An authority
   is a named human with a scope of fields and a revision number. Roles are
   `required_approver` (can block), `consulted` (must respond, cannot block), and
   `advisory` (optional).

The agent may propose authorities from repo ownership signals. It may not appoint
itself, and it may not mark a role satisfied that no human filled.

### Stage 4 — Collaborative review gate

Mandatory for every mode. The full contract is in
[review-gate.md](review-gate.md). In brief:

1. **Freeze** the ledger into a content-addressed candidate. The digest is the
   candidate's identity; editing anything produces a new candidate, never a
   mutation of the old one.
2. **Publish targeted reviewer packs.** Each reviewer receives only the slices
   their authority covers, plus specific questions — not the whole document with
   "any thoughts?".
3. **Collect feedback across channels** — chat, email, document comments,
   meetings, tickets — and normalize each item while preserving immutable
   provenance back to its original utterance.
4. **Human dispositions.** Every blocking item gets an accept, reject, modify, or
   defer decision made by a *named human*. Conflicts between reviewers are never
   resolved by the agent. Each disposition that changes the candidate records a
   **Decision Delta**.
5. **Revise with redlines**, producing a new candidate digest, then run
   **dependency-aware re-review**: only reviewers whose authority fields changed,
   plus reviewers whose fields depend on those, are asked again.
6. **Approve.** An approval names the exact candidate digest and the exact
   authority revisions it was given against. If either moves, the approval is
   stale and does not count.

Validate a review round before claiming a verdict:

```bash
bash .cursor/skills/guided-project-discovery/scripts/review-validate.sh .discovery/<slug>/review/round-<n>.md
```

### Stage 5 — Handoff

On an approved gate, hand the frozen candidate to the spine skill for the mode:

| Mode | Handoff |
|---|---|
| `research` | seed `project-researcher` Stage 0 with the candidate; it writes `.orchestrator/<slug>/RESEARCH.md` |
| `research+plan` | as above, then `project-orchestrator` Stages 1-2, stopping at its spec approval gate |
| `research+plan+execute` | as above, then `project-orchestrator` Stage 3 onward |

**Review approval and plan approval never authorize execution.** They authorize
the production of the next artifact. Execution requires the separate, explicit
human authorization at `project-orchestrator` Stage 2, given against the approved
spec. A review round that claims otherwise fails
`scripts/review-validate.sh`.

The handoff record in the ledger must name the candidate digest, the mode, the
satisfied required approvers, and — for execute mode — the fact that execution
authorization is still outstanding.

## The Discovery Ledger

`.discovery/<slug>/DISCOVERY.md` is the single source of truth for a discovery
run, and it is resumable by construction.

```text
.discovery/<slug>/
├── DISCOVERY.md                    # the ledger; lens_cursor makes it resumable
├── candidates/
│   └── <digest>/CANDIDATE.md       # frozen, immutable, content-addressed
└── review/
    └── round-<n>.md                # one file per review round
```

Schema and field rules: [reference.md](reference.md#1-discovery-ledger-schema).

## Gates and Hard Stops

- **Human gates:** mode selection (Stage 3), review approval (Stage 4), and — for
  execute mode only — execution authorization at `project-orchestrator` Stage 2.
  Three distinct gates; passing one never implies another.
- **Hard stops** (halt and report, using the
  [orchestration-kernel](../orchestration-kernel/SKILL.md#5-hard-stop-format)
  shape): a required approver is unreachable past the round budget; two required
  approvers conflict on the same field and no human will disposition it; the
  candidate digest referenced by an approval no longer exists; the interview
  oscillates without new information across the lens budget.
- **Drift detectors:** *interview drift* (asking lenses that cannot change the
  outcome), *provenance drift* (feedback recorded without a channel and source),
  *approval drift* (an approval counted against a digest it was not given for).

## Reuse Map

`pre-plan-recalibrator` (short calibration inside a single lens) ·
`codebase-investigation` (Stage 0 evidence pre-fill) · `project-researcher`
(research mode) · `project-orchestrator` (plan and execute modes) ·
`project-hardener` (post-build convergence) · `orchestration-kernel` (shared
role, evidence, and hard-stop contracts). This skill is the discovery and
review-gate front end that feeds them; it duplicates none of their internals.

## Anti-Patterns

- Dumping the whole lens bank as a questionnaire.
- Asking a lens the repository already answers.
- Holding interview state in the conversation instead of the ledger.
- Sending every reviewer the whole document with no targeted questions.
- Letting the agent resolve a disagreement between two humans.
- Editing a frozen candidate in place instead of minting a new digest.
- Counting an approval given against an earlier candidate or authority revision.
- Treating review or plan approval as permission to start building.

## Additional Resources

- Ledger schema, lens bank, mode contracts: [reference.md](reference.md)
- Collaborative review gate contract: [review-gate.md](review-gate.md)
- Sample ledger: [examples/DISCOVERY.sample.md](examples/DISCOVERY.sample.md)
- Sample review round: [examples/REVIEW.sample.md](examples/REVIEW.sample.md)
- Five pilot scenarios: [examples/pilots.md](examples/pilots.md)
- Ledger validator: [scripts/discovery-validate.sh](scripts/discovery-validate.sh)
- Review-round validator: [scripts/review-validate.sh](scripts/review-validate.sh)
- Pilot runner: [scripts/pilots-run.sh](scripts/pilots-run.sh)
