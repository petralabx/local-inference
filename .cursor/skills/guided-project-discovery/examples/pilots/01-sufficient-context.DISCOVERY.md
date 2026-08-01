---
slug: onboarding-checklist
created: 2026-07-20T13:00:00Z
updated: 2026-07-20T13:22:00Z
status: ready-for-review
mode: research
lens_cursor: done
---

# Discovery — Onboarding Checklist

Pilot 1: the requester already supplied most of the context and the repository
answered the rest. The interview short-circuits after two asked lenses and offers
an early exit rather than walking the full bank.

## Mission

New hires assemble their environment from three stale wiki pages. The initiative
is to find out whether a maintained checklist, a script, or a devcontainer is the
right answer — research only, no build commitment.

## Lenses

| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1 | Outcome | yes | answered | 2026-07-20T13:06:00Z |
| L2 | Users and jobs | yes | prefilled | 2026-07-20T13:01:00Z |
| L3 | Current reality | yes | prefilled | 2026-07-20T13:02:00Z |
| L4 | Success evidence | yes | answered | 2026-07-20T13:19:00Z |
| L5 | Constraints | no | open | — |
| L6 | Blast radius | no | waived | — |

## Answers

### L1 — Outcome

A new engineer reaches a running local stack on day one without asking anyone.
Success is recognized when the "help, setup is broken" channel goes quiet during
an onboarding week.

### L2 — Users and jobs

Prefilled from the request. Roughly one new engineer a month, plus existing staff
rebuilding a laptop two or three times a year.

### L3 — Current reality

Prefilled from the repository. Setup instructions exist in `docs/setup.md`,
`README.md`, and the internal wiki, and the three disagree about the required
Node version. There is a `.devcontainer/` directory that is referenced nowhere.

### L4 — Success evidence

One new hire completes setup unassisted, timed, with no channel messages. The
research brief must say what would be measured before anything is built.

## Assumptions

- The unreferenced `.devcontainer/` is abandoned rather than load-bearing.
  Owner: platform team. To be confirmed in research.

## Non-Goals

- Changing CI, changing the production build, or standardizing editor config.

## Evidence

- `docs/setup.md`, `README.md`, `.devcontainer/` — prefilled L3, including the
  Node version disagreement.
- The original request message — prefilled L2.

## Decision Log

- L6 (Blast radius) waived: research mode produces a document and touches no
  running system. Waived by vince.
- Early exit offered and accepted after L4. Constraints stay unasked because in
  research mode they cannot change which options the brief enumerates, only which
  one is eventually chosen.

## Handoff

- Target mode: `research`
- Candidate digest: `sha256:e0801dad5595c85c5d24741626327fc9e8c12343c424c0e518abeafda5d8d85a`
- Spine skill: `project-researcher`
- Outstanding gates: review gate at Stage 4. No plan and no execution authority is
  conferred by this handoff.
