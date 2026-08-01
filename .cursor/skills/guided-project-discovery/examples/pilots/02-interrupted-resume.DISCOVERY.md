---
slug: warehouse-cutover
created: 2026-07-22T08:30:00Z
updated: 2026-07-22T09:14:00Z
status: interviewing
mode: research+plan+execute
lens_cursor: L4
---

# Discovery — Warehouse Cutover

Pilot 2: the session was interrupted after L3. The ledger, not the conversation,
holds the state, so a later session resumes at `lens_cursor` without re-asking
anything already answered.

## Mission

The 3PL contract ends this quarter and inventory sync has to move to the new
provider. The initiative is to scope, plan, and run that cutover.

## Lenses

| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1 | Outcome | yes | answered | 2026-07-22T08:41:00Z |
| L2 | Users and jobs | yes | answered | 2026-07-22T08:58:00Z |
| L3 | Current reality | yes | prefilled | 2026-07-22T08:32:00Z |
| L4 | Constraints | yes | open | — |
| L5 | Blast radius | yes | open | — |
| L6 | Success evidence | yes | open | — |
| L7 | Non-goals | yes | open | — |
| L8 | Stakeholders | yes | open | — |

## Answers

### L1 — Outcome

Inventory levels in the storefront match the new provider's system within the
same sync window we have today, with no manual reconciliation during cutover.

### L2 — Users and jobs

Warehouse staff scan against the provider's system continuously. Two ops staff
watch the sync dashboard daily. Customers see stock levels, and a wrong level
costs an oversell.

### L3 — Current reality

Prefilled from the repository. `integrations/threepl/` holds the current adapter,
polling every 15 minutes against a SOAP endpoint, with retries in
`integrations/threepl/retry.py`. There is no replay path for a missed window.

## Assumptions

- The contract end date is fixed and cannot be extended. Owner: vince.

## Non-Goals

To be captured at L7.

## Evidence

- `integrations/threepl/` — prefilled L3 (poll interval, retry behavior, absence
  of replay).
- Signed 3PL contract in `notes/contracts/` — sourced the deadline.

## Decision Log

- Mode provisionally `research+plan+execute` because the deadline is external and
  fixed. Confirmed with the human at Stage 3; execution still requires its own
  authorization at `project-orchestrator` Stage 2.
- Session interrupted 2026-07-22T09:14Z after writing L3. Resume at L4
  (Constraints) — chosen next because a hard external deadline makes the
  constraint envelope the highest-information-gain lens remaining.

## Handoff

Not yet. Discovery is `interviewing`; five blocking lenses remain. No candidate
has been frozen, so there is nothing to review and nothing to hand off.
