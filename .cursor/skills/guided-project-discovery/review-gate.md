# Collaborative Review Gate

The contract for Stage 4 of [guided-project-discovery](SKILL.md). It applies
unchanged to `research`, `research+plan`, and `research+plan+execute` handoffs.

The gate exists because discovery output is usually reviewed by several people,
over several channels, at several times, while the document keeps changing
underneath them. Without a binding between *what was approved* and *what is being
handed off*, an approval degrades into a vague recollection that someone was fine
with an earlier draft.

## 1. Content-Addressed Candidates

A **candidate** is a frozen snapshot of the discovery ledger offered for review.

```text
.discovery/<slug>/candidates/<digest>/CANDIDATE.md
```

- The digest is `sha256` over the candidate's normalized bytes and is the
  candidate's only identity. Round numbers and timestamps are labels, not
  identity.
- Candidates are **immutable**. Responding to feedback mints a new candidate with
  a new digest; it never rewrites an existing one. The old candidate must remain
  readable, because approvals and feedback point at it.
- Every candidate records the ledger digest it was frozen from, so the chain back
  to the interview is intact.

Compute and verify a digest:

```bash
bash .cursor/skills/guided-project-discovery/scripts/review-validate.sh --digest .discovery/<slug>/candidates/<digest>/CANDIDATE.md
```

If the recomputed digest does not equal the directory name, the candidate has
been mutated in place. That is a hard stop, not a warning.

## 2. Authorities and Field-Specific Scope

An **authority** is a named human who owns a defined set of candidate fields.

```text
| Authority | Owner            | Fields                        | Revision |
|-----------|------------------|-------------------------------|----------|
| AUTH-SEC  | dana@example.com | threat-model, data-handling   | 3        |
```

- Authority is **field-specific**. A security owner's approval covers the security
  fields and says nothing about scope or budget.
- The **revision** increments whenever that authority's own governing policy
  changes — a new security standard, a revised budget ceiling. A revision bump
  invalidates approvals given under the older revision, because the reviewer
  approved against rules that no longer hold.
- Every blocking field must be covered by exactly one authority. An uncovered
  blocking field is a hard stop; two authorities claiming the same field is a
  hard stop.

## 3. Reviewer Roles

| Role | Must respond | Can block | Counts toward the gate |
|---|---|---|---|
| `required_approver` | yes | yes | yes — all must approve |
| `consulted` | yes | no | response required, verdict advisory |
| `advisory` | no | no | no |

At least one `required_approver` is mandatory. Silence from a `required_approver`
is never an approval; past the round budget it is a hard stop, escalated to the
accountable human.

## 4. Targeted Reviewer Packs

Each reviewer receives a pack containing only their authority's slices of the
candidate plus specific questions. A reviewer pack that is the whole document with
"let me know what you think" is a defect — it produces either silence or scattered
commentary outside the reviewer's competence.

```markdown
### Reviewer dana@example.com — required_approver
- Authority: AUTH-SEC (revision 3)
- Scope: threat-model, data-handling
- Questions:
  - Q1: Does the proposed tenant isolation boundary satisfy standard 3.2?
  - Q2: Is 30-day retention acceptable for the derived index?
```

Questions must be answerable from the pack, and must be specific enough that a
one-word answer is meaningful.

## 5. Multi-Channel Feedback Normalization

Feedback arrives through chat, email, document comments, meetings, and tickets.
Each item is normalized into a common shape while preserving **immutable
provenance** back to the original utterance.

```markdown
### F2
- Reviewer: dana@example.com
- Channel: meeting
- Received: 2026-07-29T15:04:00Z
- Provenance: notes/2026-07-29-security-sync.md#L44-L51
- Against: sha256:6b1f…
- Field: data-handling
- Type: blocking
- Verbatim: "Thirty days is too long if we're keeping raw payloads."
- Normalized: Retention of 30 days is unacceptable for raw payloads; derived
  fields may differ.
```

Rules:

- `Against` names the candidate digest the reviewer actually saw. Feedback on a
  superseded candidate is still valid input; it is simply not feedback on the
  current one, and the difference must stay visible.
- `Verbatim` is never edited. Normalization is additive.
- Provenance must resolve to something durable. "Someone mentioned in standup" is
  not provenance.
- Two reviewers saying the same thing are two items. Feedback is not deduplicated,
  because agreement between authorities is itself information.

## 6. Human-Owned Dispositions and Decision Deltas

Every `blocking` feedback item requires a **disposition** decided by a named
human. The agent drafts options and consequences; it does not decide.

```markdown
### D2 -> F2
- Decided By: vince@petrasoap.com
- Decision: modify
- Rationale: Raw payloads drop to 7 days; derived index keeps 30.
- Decision Delta: data-handling retention 30d -> raw 7d / derived 30d
```

| Decision | Meaning |
|---|---|
| `accept` | the candidate changes as the reviewer asked |
| `reject` | the candidate stands; rationale is recorded and returned to the reviewer |
| `modify` | a third option is adopted |
| `defer` | recorded as a follow-up with an owner; must not block a mode it cannot affect |

A **Decision Delta** is the durable record of what the candidate's content owes to
which piece of feedback. It states the field and the before/after, so the next
reader can reconstruct why the approved candidate differs from the first draft
without replaying the whole thread.

**Conflicts between reviewers are always escalated, never averaged.** When two
required approvers disagree on the same field, the agent presents both positions,
their consequences, and the fields affected, then stops until the accountable
human dispositions it.

## 7. Redlines and Dependency-Aware Re-Review

Revision produces a new candidate plus an explicit redline set:

```markdown
## Redlines
- data-handling: retention 30d -> raw 7d / derived 30d (from D2)
- threat-model: added payload-at-rest boundary (from D2)
```

Re-review is **targeted, not global**. Ask again only:

1. reviewers whose authority covers a redlined field, and
2. reviewers whose authority fields **depend on** a redlined field, per the
   declared dependency edges.

```markdown
## Re-Review
- Triggered For: dana@example.com, priya@example.com
- Reason: authority-field-changed (dana), dependency-changed (priya)
- Dependencies: cost-model depends on data-handling
```

Reviewers untouched by the redlines keep their existing approvals, provided those
approvals are not stale by the rule below. Re-reviewing everyone on every round is
how review fatigue turns into rubber-stamping.

## 8. Candidate-Bound Approvals

An approval names both the candidate digest and the authority revisions it was
given under.

```markdown
### A1
- Reviewer: dana@example.com
- Role: required_approver
- Approves Candidate: sha256:6b1f…
- Authority Revisions: AUTH-SEC@3
- At: 2026-07-29T16:20:00Z
- Scope Limit: does-not-authorize-execution
```

An approval is **stale**, and does not count toward the gate, when either:

- the current candidate digest differs from `Approves Candidate`, or
- any named authority's current revision differs from the approved revision.

Staleness is mechanical. `scripts/review-validate.sh` fails a round whose
approvals do not match the round's candidate digest, so a stale approval cannot be
counted by accident.

## 9. Gate Verdict

```markdown
## Gate Result
- Required Approvers Satisfied: 2/2
- Stale Approvals: none
- Verdict: approved-for-research+plan
- Execution Authorized: no
```

The verdict is `approved-for-<mode>` only when every `required_approver` has a
non-stale approval against the current candidate and every `consulted` reviewer
has responded. Otherwise the verdict is `blocked`, with the missing items named.

## 10. Review Approval Never Authorizes Execution

This is the hard prohibition, and it is enforced mechanically.

- A review gate authorizes the **production of the next artifact** for the
  approved mode. Nothing else.
- Plan approval — including `project-orchestrator`'s Stage 2 spec approval — is an
  approval of a plan's *content*. Execution authorization is a separate, explicit
  human act, given against the approved spec, recorded separately.
- `Execution Authorized: yes` is not a legal value in a review round.
  `scripts/review-validate.sh` treats it as a failure regardless of how many
  approvals the round carries, and every approval must carry the
  `Scope Limit: does-not-authorize-execution` line.

The rule exists because the alternative fails silently: a reviewer who approves a
document reasonably believes they approved a document, and discovers otherwise
only after something has been built and deployed on the strength of their
sign-off.
