---
slug: sharepoint-doc-org-harness
round: 1
candidate_digest: sha256:dad95238b668846b124ea0651d5d9d072a1571b1d258a7a515393ade47602d8c
mode: research+plan+execute
status: superseded
---

# Review Round 1 — SharePoint Document Organization Harness

Sole-approver gate for Vince. Superseded by round 2 after an accepted modify
(OSS reuse research mandate).

## Candidate Manifest

- Digest: sha256:dad95238b668846b124ea0651d5d9d072a1571b1d258a7a515393ade47602d8c
- Frozen At: 2026-08-12T11:00:00Z
- Source Ledger: .discovery/sharepoint-doc-org-harness/DISCOVERY.md
- Supersedes: none
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-OWNER | cos@petrasoap.com (Vince) | mission, mode, outcome, users-jobs, constraints, blast-radius, success-evidence, non-goals, stakeholders, operations-intent, local-only-runtime | 1 |

Dependency edges: none (single authority covers all blocking fields).

## Reviewer Pack

### Reviewer cos@petrasoap.com — required_approver
- Authority: AUTH-OWNER (revision 1)
- Scope: mission, mode, outcome, users-jobs, constraints, blast-radius, success-evidence, non-goals, stakeholders, operations-intent, local-only-runtime
- Questions:
  - Q1: Approve mode `research+plan+execute` knowing review approval does **not** authorize building until a later explicit execution gate?
  - Q2: Approve **wide auto** with easy reverse + knowledge-graph provenance as the safety model (no gated crawl/walk/run)?
  - Q3: Approve scope: VincePersonal files + Outlook folders/rules + attachments; exclude code/repos and team SharePoint; archive beyond research horizon?
  - Q4: Approve hard constraint: after the harness is built, **all** steady-state maintenance and organizing agents use **local LiteLLM lanes only** (Qwen/Ornith) with **zero paid cloud LLM tokens**?
  - Q5: Approve retain/discard judgment: keep taxonomy/naming/correction_rules; replace Claude Cowork runtime?

## Feedback

### F1
- Reviewer: cos@petrasoap.com
- Channel: chat
- Received: 2026-08-12T11:00:00Z
- Provenance: cursor-chat/guided-project-discovery/sharepoint-doc-org-harness#stage4-q1-q5
- Against: sha256:dad95238b668846b124ea0651d5d9d072a1571b1d258a7a515393ade47602d8c
- Field: constraints
- Type: blocking
- Verbatim: "This is good, can you include external research of opensource github repos that might help in minimizing the amount of code we need to build? Tools that might help our effort here that are well maintained with lots of stars?"
- Normalized: Approve Q1–Q5 shape; require research to survey high-star maintained OSS and prefer reuse over greenfield.

## Dispositions

### D1 -> F1
- Decided By: cos@petrasoap.com
- Decision: modify
- Rationale: Keep approved shape; add OSS reuse mandate + seeded shortlist; mint new candidate for re-approval of the delta.
- Decision Delta: constraints += OSS reuse survey; answers += OSS reuse mandate shortlist; research handoff requires adopt/wrap/reject table

## Redlines

- constraints: add OSS reuse survey (high-star GitHub) before greenfield
- research-handoff: require adopt/wrap/reject table
- answers: seeded OSS shortlist (Docling, Paperless-ngx, OCRmyPDF, fclones, Graph SDKs, Neo4j/Memgraph, Qdrant/LanceDB, TagSpaces, Karakeep)

## Re-Review

- Triggered For: cos@petrasoap.com
- Reason: authority-field-changed (constraints / research-handoff)
- Dependencies: none
- Next round: round-2 against sha256:0f053485230e80ef881c98f39430074a4e1e676412cf7381547f19c747e97902

## Approvals

_(none — modified before approval closed)_

## Verdict

- Status: superseded
- Note: execution authorization remains prohibited.
