---
slug: tenant-usage-reporting
round: 2
candidate_digest: sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa
mode: research+plan
status: approved
---

# Review Round 2 — Tenant Usage Reporting

Round 1 surfaced a blocking retention objection and a cost concern that depended
on it. This round reviews the revised candidate.

## Candidate Manifest

- Digest: sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa
- Frozen At: 2026-07-29T12:00:00Z
- Source Ledger: .discovery/tenant-usage-reporting/DISCOVERY.md@sha256:e7662c52c067e66e4c6dbf993c62454b5706406f29dab0b663d5bfa4376c56fa
- Supersedes: sha256:e1411851faaa9dcb1b0954d1ca3f121467ccbe5b2b10355427ef895cd2f3d0bf
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-SEC | dana@example.com | threat-model, data-handling | 3 |
| AUTH-COST | priya@example.com | cost-model, warehouse-spend | 1 |
| AUTH-CS | marcus@example.com | usability, rollout | 2 |

Dependency edges: `cost-model` depends on `data-handling`.

## Reviewer Pack

### Reviewer dana@example.com — required_approver
- Authority: AUTH-SEC (revision 3)
- Scope: threat-model, data-handling
- Questions:
  - Q1: Does raw-payload retention of 7 days satisfy standard 3.2?
  - Q2: Is the derived index free of customer-identifying fields?

### Reviewer priya@example.com — required_approver
- Authority: AUTH-COST (revision 1)
- Scope: cost-model, warehouse-spend
- Questions:
  - Q1: With raw retention cut to 7 days, does the projected monthly warehouse spend stay under the policy ceiling?

### Reviewer marcus@example.com — consulted
- Authority: AUTH-CS (revision 2)
- Scope: usability, rollout
- Questions:
  - Q1: Is a current-and-previous-period view enough for a renewal call, or do reps need a trailing year?

## Feedback

### F1
- Reviewer: dana@example.com
- Channel: meeting
- Received: 2026-07-29T15:04:00Z
- Provenance: notes/2026-07-29-security-sync.md#L44-L51
- Against: sha256:e1411851faaa9dcb1b0954d1ca3f121467ccbe5b2b10355427ef895cd2f3d0bf
- Field: data-handling
- Type: blocking
- Verbatim: "Thirty days is too long if we're keeping raw payloads."
- Normalized: 30-day retention is unacceptable for raw payloads; derived fields may differ.

### F2
- Reviewer: priya@example.com
- Channel: email
- Received: 2026-07-29T15:40:00Z
- Provenance: mail/AAMkAGI2-2026-07-29-warehouse-spend.eml
- Against: sha256:e1411851faaa9dcb1b0954d1ca3f121467ccbe5b2b10355427ef895cd2f3d0bf
- Field: cost-model
- Type: concern
- Verbatim: "Whatever retention you land on, I need the spend line recomputed before I sign."
- Normalized: Cost model must be recomputed against the final retention decision before approval.

### F3
- Reviewer: marcus@example.com
- Channel: chat
- Received: 2026-07-29T16:02:00Z
- Provenance: slack/C04CS/p1785400920
- Against: sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa
- Field: usability
- Type: suggestion
- Verbatim: "Two periods covers renewals. A trailing year would be nice later, not now."
- Normalized: Current-and-previous period is sufficient for the renewal job; trailing year is a follow-up.

## Dispositions

### D1 -> F1
- Decided By: vince@petrasoap.com
- Decision: modify
- Rationale: Raw payloads are only needed for reprocessing, which finishes inside a week. The derived index carries no payload content, so it can keep 30 days without the same exposure.
- Decision Delta: data-handling retention 30d -> raw 7d / derived 30d

### D2 -> F2
- Decided By: vince@petrasoap.com
- Decision: accept
- Rationale: The retention change moves the spend line, and priya owns that field. Cost model recomputed against 7d/30d before this round was published.
- Decision Delta: cost-model projected monthly spend 1,840 -> 1,190

### D3 -> F3
- Decided By: vince@petrasoap.com
- Decision: defer
- Rationale: Trailing-year history does not affect the renewal job that justifies this work. Recorded as a follow-up rather than widening scope now.
- Decision Delta: none

## Redlines

- data-handling: retention 30d -> raw 7d / derived 30d (from D1)
- threat-model: added payload-at-rest boundary for the 7-day window (from D1)
- cost-model: projected monthly spend 1,840 -> 1,190 (from D2)

## Re-Review

- Triggered For: dana@example.com, priya@example.com
- Reason: authority-field-changed (dana, data-handling and threat-model), dependency-changed (priya, cost-model depends on data-handling)
- Dependencies: cost-model depends on data-handling
- Not Re-Reviewed: marcus@example.com — no redline touches usability or rollout

## Approvals

### A1
- Reviewer: dana@example.com
- Role: required_approver
- Approves Candidate: sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa
- Authority Revisions: AUTH-SEC@3
- At: 2026-07-29T17:10:00Z
- Scope Limit: does-not-authorize-execution

### A2
- Reviewer: priya@example.com
- Role: required_approver
- Approves Candidate: sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa
- Authority Revisions: AUTH-COST@1
- At: 2026-07-29T17:38:00Z
- Scope Limit: does-not-authorize-execution

## Gate Result

- Required Approvers Satisfied: 2/2
- Consulted Responded: 1/1
- Stale Approvals: none
- Verdict: approved-for-research+plan
- Execution Authorized: no
- Note: this gate authorizes production of the research brief and spec only.
  Building requires the separate execution authorization at
  `project-orchestrator` Stage 2.
