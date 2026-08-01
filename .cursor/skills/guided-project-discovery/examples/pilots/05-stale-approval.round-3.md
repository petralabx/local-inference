---
slug: billing-export
round: 3
candidate_digest: sha256:aee9e4bbc745f0fc505c8c2ab41ca64213ffa6fc11fcdd9a69b384e268462860
mode: research+plan
status: approved
---

# Review Round 3 — Billing Export (INTENTIONALLY INVALID)

Pilot 5 is a **negative fixture** covering the two ways an approval goes stale.
Both are the same underlying error — counting a sign-off given against something
other than what is now being handed off — and both must be caught mechanically,
because neither is visible to someone skimming the round.

Expected failures:

1. `A1` approves the round-2 candidate. The candidate was redlined since, so the
   digest moved and dana never saw the current text.
2. `A2` was given under `AUTH-SEC@3`, but `AUTH-SEC` is now at revision 4 — the
   security standard changed after the approval, so it was given against rules
   that no longer hold.
3. With both approvals stale, no required approver is satisfied, yet the round
   claims `status: approved`.

## Candidate Manifest

- Digest: sha256:aee9e4bbc745f0fc505c8c2ab41ca64213ffa6fc11fcdd9a69b384e268462860
- Frozen At: 2026-07-27T08:00:00Z
- Source Ledger: .discovery/billing-export/DISCOVERY.md@sha256:e0801dad5595c85c5d24741626327fc9e8c12343c424c0e518abeafda5d8d85a
- Supersedes: sha256:9e51186210ddbc01342448d79067d69c88895107fe8ec20c1ca4164f67e4df85
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-FIN | priya@example.com | export-format, reconciliation | 1 |
| AUTH-SEC | dana@example.com | data-handling | 4 |

## Reviewer Pack

### Reviewer priya@example.com — required_approver
- Authority: AUTH-FIN (revision 1)
- Scope: export-format, reconciliation
- Questions:
  - Q1: Does the revised column set still reconcile against the ledger export?

### Reviewer dana@example.com — required_approver
- Authority: AUTH-SEC (revision 4)
- Scope: data-handling
- Questions:
  - Q1: Under standard 4.0, is a 90-day export retention still acceptable?

## Feedback

### F1
- Reviewer: priya@example.com
- Channel: chat
- Received: 2026-07-26T16:10:00Z
- Provenance: slack/C04FIN/p1785300610
- Against: sha256:9e51186210ddbc01342448d79067d69c88895107fe8ec20c1ca4164f67e4df85
- Field: reconciliation
- Type: blocking
- Verbatim: "Credit notes aren't in this export, so it will never tie out."
- Normalized: Export omits credit notes and therefore cannot reconcile to the ledger.

## Dispositions

### D1 -> F1
- Decided By: vince@petrasoap.com
- Decision: accept
- Rationale: Reconciliation is the point of the export; omitting credit notes defeats it.
- Decision Delta: reconciliation added credit_note rows to the export scope

## Redlines

- reconciliation: added credit_note rows (from D1)
- data-handling: export now carries credit-note references (from D1)

## Re-Review

- Triggered For: priya@example.com, dana@example.com
- Reason: authority-field-changed (priya, reconciliation), dependency-changed (dana, data-handling depends on reconciliation)
- Dependencies: data-handling depends on reconciliation

## Approvals

### A1
- Reviewer: dana@example.com
- Role: required_approver
- Approves Candidate: sha256:9e51186210ddbc01342448d79067d69c88895107fe8ec20c1ca4164f67e4df85
- Authority Revisions: AUTH-SEC@4
- At: 2026-07-26T11:00:00Z
- Scope Limit: does-not-authorize-execution

### A2
- Reviewer: priya@example.com
- Role: required_approver
- Approves Candidate: sha256:aee9e4bbc745f0fc505c8c2ab41ca64213ffa6fc11fcdd9a69b384e268462860
- Authority Revisions: AUTH-FIN@1, AUTH-SEC@3
- At: 2026-07-27T09:30:00Z
- Scope Limit: does-not-authorize-execution

## Gate Result

- Required Approvers Satisfied: 2/2
- Stale Approvals: none
- Verdict: approved-for-research+plan
- Execution Authorized: no
