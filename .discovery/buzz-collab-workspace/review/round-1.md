---
slug: buzz-collab-workspace
round: 1
candidate_digest: sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
mode: research+plan
status: open
---

# Review Round 1 — Buzz Collaboration Workspace

Frozen discovery ledger offered for collaborative review. Mode is
**research+plan** (research brief + approved SPEC only — no build execution).

## Candidate Manifest

- Digest: sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
- Frozen At: 2026-08-06T09:57:00Z
- Source Ledger: .discovery/buzz-collab-workspace/DISCOVERY.md@sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
- Supersedes: —
- Immutable: true

## Authorities

| Authority | Owner | Fields | Revision |
|-----------|-------|--------|----------|
| AUTH-DECISION | Vince | outcome, mode, non-goals, stakeholders, users | 1 |
| AUTH-INFRA | Vince | constraints, blast-radius, hosting | 1 |
| AUTH-PORTAL | Ricardo | success-evidence, current-reality, portal-orbit | 1 |
| AUTH-PILOT | Stephen | usability, pilot-participation | 1 |

Dependency edges: success-evidence depends on portal-orbit; blast-radius
depends on hosting.

## Reviewer Pack

### Reviewer Vince — required_approver
- Authority: AUTH-DECISION@1, AUTH-INFRA@1
- Scope: outcome, mode, non-goals, stakeholders, users, constraints, blast-radius, hosting
- Questions:
  - Q1: Confirm mode research+plan (brief + SPEC, no execute) is correct for this handoff?
  - Q2: Confirm EC2+Compose for pilot (Dell = agent worker only) and L5 scoped-tool fence?
  - Q3: Confirm COS Seal / Agent Registry bridge stays out of v1 as the #1 post-pilot adapter?

### Reviewer Ricardo — required_approver
- Authority: AUTH-PORTAL@1
- Scope: success-evidence, current-reality, portal-orbit
- Questions:
  - Q1: Is plx-customer-portal + Mission Control the right pilot orbit (Buzz as room, MC as PM SoR)?
  - Q2: Is success = room works + one real portal project completed in Buzz, signed by you + Vince, acceptable?
  - Q3: Any portal reality the prefilled L3 missed that would change the plan?

### Reviewer Stephen — consulted
- Authority: AUTH-PILOT@1
- Scope: usability, pilot-participation
- Questions:
  - Q1: Will you join the pilot as a daily-ish Buzz participant with your primary agent?
  - Q2: Any usability blocker (Tailscale/access/client) that must be solved before stand-up?

## Feedback

_(none yet — awaiting reviewer responses)_

## Dispositions

_(none yet)_

## Redlines

_(none yet — no candidate revision in this open round)_

## Re-Review

_(none yet — no fields changed)_

## Approvals

_(none yet — required: Vince, Ricardo)_

## Gate Result

- Required Approvers Satisfied: 0/2
- Consulted Responded: 0/1
- Stale Approvals: none
- Verdict: open-awaiting-reviewers
- Execution Authorized: no
- Note: this gate, when approved, authorizes writing the research brief and
  SPEC only. Building is out of mode for research+plan.
