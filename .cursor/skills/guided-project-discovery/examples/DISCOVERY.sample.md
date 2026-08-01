---
slug: tenant-usage-reporting
created: 2026-07-28T09:00:00Z
updated: 2026-07-29T14:05:00Z
status: in-review
mode: research+plan
lens_cursor: done
---

# Discovery — Tenant Usage Reporting

## Mission

Customer-success staff cannot answer "how much is this tenant actually using?"
without asking engineering to run a query. The initiative is to give CS a
self-serve view of per-tenant usage that is trustworthy enough to quote to a
customer during a renewal conversation.

## Lenses

| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1 | Outcome | yes | answered | 2026-07-28T09:12:00Z |
| L2 | Users and jobs | yes | answered | 2026-07-28T09:26:00Z |
| L3 | Current reality | yes | prefilled | 2026-07-28T09:04:00Z |
| L4 | Constraints | yes | answered | 2026-07-28T10:02:00Z |
| L5 | Success evidence | yes | answered | 2026-07-28T10:18:00Z |
| L6 | Non-goals | yes | answered | 2026-07-28T10:31:00Z |
| L7 | Stakeholders | yes | answered | 2026-07-29T09:40:00Z |
| L8 | Blast radius | no | answered | 2026-07-29T09:55:00Z |
| L9 | Alternatives | no | waived | — |
| L10 | Taste | no | open | — |

## Answers

### L1 — Outcome

A CS rep can open a tenant and see usage for the current and previous billing
period without filing a ticket. Success is recognized when engineering stops
receiving ad-hoc usage queries.

### L2 — Users and jobs

Primary: 6 CS reps, several times a day during renewal season. Secondary: 2
finance staff at month end, who need the same numbers to reconcile invoices.
Reps need speed; finance needs the number to match billing exactly.

### L3 — Current reality

Prefilled from the repository at Stage 0. Usage events land in `events_raw` and
are aggregated nightly by `jobs/usage_rollup.py` into `usage_daily`. There is no
per-tenant read path outside the admin console, and the rollup has no backfill.

### L4 — Constraints

No new datastore. Must reuse the existing warehouse. Read path must not touch the
billing service directly. Numbers shown to a customer must be reproducible from
stored data, not recomputed on the fly.

### L5 — Success evidence

CS reps quote a number in three real renewal calls without escalating, and the
quoted figure matches the invoice for the same period. Verified by comparing the
reporting view against finance's month-end reconciliation for two periods.

### L6 — Non-goals

Not building forecasting, not changing how usage is metered, not exposing this to
customers directly, not touching the invoice generation path.

### L7 — Stakeholders

Approves: dana (security and data handling), priya (cost and warehouse spend).
Consulted: marcus (CS lead, owns whether the view is usable). Informed: finance.

### L8 — Blast radius

Read-only over an existing warehouse table. No production write path, no auth
changes, no customer-facing surface. Reversible by removing the view.

## Assumptions

- The nightly rollup is accurate enough for renewal conversations. Owner: priya.
  To be confirmed against one month of reconciliation before the plan is final.
- Six reps is the steady-state user count. Owner: marcus.

## Non-Goals

- Forecasting or projected usage.
- Changes to metering, invoicing, or the billing service.
- A customer-facing usage page.

## Evidence

- `jobs/usage_rollup.py` and `schema/usage_daily.sql` — prefilled L3 (current
  aggregation shape, absence of backfill).
- `docs/warehouse-cost-policy.md` — sourced the warehouse spend constraint in L4.
- Renewal-call transcripts in `notes/cs-renewals/` — sourced the L5 verification
  approach.

## Decision Log

- L9 (Alternatives) waived: no prior attempt exists and the option space is
  narrow enough that the research brief will enumerate it. Waived by vince.
- Mode set to `research+plan` rather than `research+plan+execute`: the rollup
  accuracy assumption must be confirmed before anyone commits to building.
- Reporting reads from `usage_daily`, not `events_raw`, because L4 requires the
  quoted number to be reproducible from stored data.

## Handoff

- Target mode: `research+plan`
- Candidate digest: `sha256:a6957e0f45adda5d40b9d1d9cee5311fbadb29076feaa0086c3bcf4925229daa`
- Review round: `.discovery/tenant-usage-reporting/review/round-2.md`
- Spine skill: `project-researcher`, then `project-orchestrator` Stages 1-2
- Outstanding gates: `project-orchestrator` Stage 2 spec approval. Execution is
  not in scope for this mode and is not authorized by the review gate.
