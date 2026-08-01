---
slug: billing-export
round: 1
candidate_digest: sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
mode: research+plan
status: approved
---

# Review Round 1 — Billing Export (INTENTIONALLY INVALID)

Pilot 4 is a **negative fixture**. It is a fully-approved, otherwise well-formed
plan-mode review round that tries to convert its approvals into permission to
build. `scripts/review-validate.sh` must reject it.

Expected failures:

1. `## Gate Result` sets `Execution Authorized` to `yes`.
2. `A2` replaces the mandatory scope limit with `authorizes-execution`.

The `Execution Authorized` check runs over every line rather than only the gate
section, so the prohibition cannot be evaded by moving the claim elsewhere in the
round.

This is the failure mode the prohibition exists for. Two reviewers approved a
*document*; nothing here is a human authorizing a deployment, yet the round is
shaped so a downstream reader would treat it as one.

## Candidate Manifest

- Digest: sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
- Frozen At: 2026-07-25T09:00:00Z
- Source Ledger: .discovery/billing-export/DISCOVERY.md@sha256:e0801dad5595c85c5d24741626327fc9e8c12343c424c0e518abeafda5d8d85a
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-FIN | priya@example.com | export-format, reconciliation | 1 |
| AUTH-SEC | dana@example.com | data-handling | 2 |

## Reviewer Pack

### Reviewer priya@example.com — required_approver
- Authority: AUTH-FIN (revision 1)
- Scope: export-format, reconciliation
- Questions:
  - Q1: Does the proposed CSV column set reconcile against the ledger export?

### Reviewer dana@example.com — required_approver
- Authority: AUTH-SEC (revision 2)
- Scope: data-handling
- Questions:
  - Q1: Is the export free of stored card identifiers?

## Feedback

### F1
- Reviewer: priya@example.com
- Channel: ticket
- Received: 2026-07-25T10:30:00Z
- Provenance: jira/FIN-1182#comment-3
- Against: sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
- Field: export-format
- Type: suggestion
- Verbatim: "Add the period end date as its own column so pivot tables don't have to parse it."
- Normalized: Emit period_end as a discrete column rather than embedding it in a label.

## Dispositions

### D1 -> F1
- Decided By: vince@petrasoap.com
- Decision: accept
- Rationale: Trivial change, removes a parsing step for every consumer.
- Decision Delta: export-format added period_end column

## Redlines

- export-format: added period_end column (from D1)

## Re-Review

- Triggered For: priya@example.com
- Reason: authority-field-changed (export-format)
- Dependencies: none

## Approvals

### A1
- Reviewer: priya@example.com
- Role: required_approver
- Approves Candidate: sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
- Authority Revisions: AUTH-FIN@1
- At: 2026-07-25T14:00:00Z
- Scope Limit: does-not-authorize-execution

### A2
- Reviewer: dana@example.com
- Role: required_approver
- Approves Candidate: sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
- Authority Revisions: AUTH-SEC@2
- At: 2026-07-25T14:20:00Z
- Scope Limit: authorizes-execution

## Gate Result

- Required Approvers Satisfied: 2/2
- Stale Approvals: none
- Verdict: approved-for-research+plan
- Execution Authorized: yes
