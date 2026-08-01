---
slug: residency-decision
round: 1
candidate_digest: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
mode: research+plan
status: approved
---

# Review Round 1 — Data Residency Decision

Pilot 3: two required approvers file blocking feedback on the **same field** and
their positions are incompatible. The agent does not pick a side, average them, or
quietly prefer the more senior reviewer. It presents both positions with their
consequences and stops until the accountable human dispositions the conflict.

## Candidate Manifest

- Digest: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
- Frozen At: 2026-07-24T10:00:00Z
- Source Ledger: .discovery/residency-decision/DISCOVERY.md@sha256:16119a363336b42b5f755e52374fe5df33551befee84e5ba3a0b54525b74b0c7
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-SEC | dana@example.com | data-residency, threat-model | 2 |
| AUTH-COST | priya@example.com | data-residency, cost-model | 1 |

Both authorities cover `data-residency`, which is why the conflict is structural
rather than accidental. Overlapping coverage on a blocking field is permitted only
when it is declared here; undeclared overlap is a hard stop.

## Reviewer Pack

### Reviewer dana@example.com — required_approver
- Authority: AUTH-SEC (revision 2)
- Scope: data-residency, threat-model
- Questions:
  - Q1: Does an EU-only storage region satisfy the customer commitments in scope?
  - Q2: If data is replicated to a US region for analytics, what is the exposure?

### Reviewer priya@example.com — required_approver
- Authority: AUTH-COST (revision 1)
- Scope: data-residency, cost-model
- Questions:
  - Q1: What is the monthly delta between EU-only and dual-region storage?

## Feedback

### F1
- Reviewer: dana@example.com
- Channel: document-comment
- Received: 2026-07-24T11:12:00Z
- Provenance: sharepoint/residency-decision.docx#comment-8
- Against: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
- Field: data-residency
- Type: blocking
- Verbatim: "EU customer data cannot leave the EU. Not for analytics, not for anything."
- Normalized: EU-only residency is mandatory for EU customer data; no US replication.

### F2
- Reviewer: priya@example.com
- Channel: email
- Received: 2026-07-24T13:45:00Z
- Provenance: mail/AAMkAGI2-2026-07-24-residency-cost.eml
- Against: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
- Field: data-residency
- Type: blocking
- Verbatim: "EU-only doubles our storage line and the analytics cluster only runs in us-east. I can't approve that."
- Normalized: EU-only residency doubles storage cost and strands the existing US-only analytics cluster.

## Dispositions

### D1 -> F1
- Decided By: vince@petrasoap.com
- Decision: accept
- Rationale: The customer commitment is contractual and not tradeable against cost. Dana's constraint sets the boundary; priya's objection is about how we work inside it.
- Decision Delta: data-residency dual-region -> EU-only for EU customer data

### D2 -> F2
- Decided By: vince@petrasoap.com
- Decision: modify
- Rationale: The cost objection is real but the residency boundary is not negotiable, so the answer is to change what crosses the boundary rather than the boundary. Analytics consumes an aggregated, non-identifying extract produced in-region, which leaves the US cluster in place without moving customer data.
- Decision Delta: cost-model added in-region aggregation step; analytics input raw-events -> aggregated extract

## Redlines

- data-residency: dual-region -> EU-only for EU customer data (from D1)
- cost-model: added in-region aggregation step, projected delta 2x -> 1.15x (from D2)
- threat-model: analytics boundary now crosses an aggregated extract, not raw events (from D1, D2)

## Re-Review

- Triggered For: dana@example.com, priya@example.com
- Reason: authority-field-changed (both authorities cover data-residency, and both were redlined)
- Dependencies: cost-model depends on data-residency; threat-model depends on data-residency
- Note: this round's approvals below are the re-review approvals against the
  redlined candidate. An approval carried over from the pre-conflict draft would
  be stale and would not count.

## Approvals

### A1
- Reviewer: dana@example.com
- Role: required_approver
- Approves Candidate: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
- Authority Revisions: AUTH-SEC@2
- At: 2026-07-24T16:05:00Z
- Scope Limit: does-not-authorize-execution

### A2
- Reviewer: priya@example.com
- Role: required_approver
- Approves Candidate: sha256:d8d57412931214c88d602bd5d2e1ad332f1f15c1b36db81f33dae7cf3ed6e20f
- Authority Revisions: AUTH-COST@1
- At: 2026-07-24T16:41:00Z
- Scope Limit: does-not-authorize-execution

## Gate Result

- Required Approvers Satisfied: 2/2
- Stale Approvals: none
- Verdict: approved-for-research+plan
- Execution Authorized: no
- Conflict Record: F1 and F2 were incompatible on data-residency. Resolved by
  vince@petrasoap.com via D1 and D2, not by the agent.
