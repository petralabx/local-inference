---
name: vmc-output-autoresearch
description: Runs a non-ML, archetype-based research-to-output loop for polished artifacts such as growth sites, technical architecture, content engines, and competitive intelligence. Use when the user asks for AutoResearch outside closed-loop ML reliability work, wants research-driven iteration, or wants an artifact produced and evaluated against archetype gates.
---

# VMC Output AutoResearch

Use this skill to turn research into a polished, evaluated output. This is the
general non-ML AutoResearch loop: report-only when the user wants intelligence,
implementation-capable when the user approves production.

## When To Use

- The user asks for AutoResearch outside the ML closed-loop reliability domains.
- The output is a website, landing page, report, architecture plan, content hub,
  competitor teardown, sales asset, SOP, or campaign plan.
- The user wants iterative improvement until an eval gate passes.
- The task benefits from research, synthesis, production, and verification.

## When Not To Use

- ML closed-loop VMC reliability projects; use `vmc-autoresearch-core`.
- Simple one-shot answers with no artifact or iteration.
- Tasks where the user has not approved edits and the requested mode is unclear.

## Core Loop

```text
Output AutoResearch Progress
- [ ] 1) Classify archetype and execution mode
- [ ] 2) Frame goal, audience, constraints, and success gates
- [ ] 3) Gather evidence through VMC report-only AutoResearch, web/source research, repo context, or user material
- [ ] 4) Synthesize into a spec, strategy, or implementation plan
- [ ] 5) Produce the artifact only if execution mode allows edits
- [ ] 6) Evaluate with archetype gates
- [ ] 7) Polish in bounded loops until gates pass or a stop condition fires
- [ ] 8) Handoff evidence, residual risks, and next actions
```

## Execution Modes

- `report-only`: research and synthesize only. Do not edit artifacts.
- `produce-with-approval`: produce the artifact after the user approves a plan.
- `iterate-to-gate`: produce, evaluate, polish, and stop only when gates pass or
  a blocker is documented.

If the user does not specify mode, default to `report-only` for external or
strategic work and `produce-with-approval` for explicit implementation requests.

## MVP Archetypes

### `growth-site`

Use for public websites, landing pages, SEO pages, and campaign pages.

Research lanes:
- Customer intent and personas
- SEO keyword clusters and search intent
- Competitor teardown
- Paid ads and landing-page angles
- Conversion objections and proof points
- Claim safety and source grounding

Eval gates:
- Routes render and links work
- Metadata, headings, internal links, and structured data are reviewed
- Mobile and desktop visual QA pass
- Accessibility basics pass
- Performance/build checks pass where tooling exists
- Claims are grounded or clearly future-facing
- CTA path and objection handling are strong

### `technical-architecture`

Use for RFCs, migration plans, system designs, and integration proposals.

Research lanes:
- Existing architecture and constraints
- Prior art and vendor patterns
- Risk and dependency map
- Security, privacy, and operations impact
- Rollback and migration strategy

Eval gates:
- Current-state evidence cited
- Proposed-state flow is explicit
- Trade-offs and alternatives are documented
- Rollback and verification plan exist
- Security and data-boundary risks are addressed

### `content-engine`

Use for blog clusters, SEO hubs, help centers, docs, and knowledge bases.

Research lanes:
- Audience questions
- Keyword clusters
- Editorial hierarchy
- Internal linking model
- Source and claim evidence

Eval gates:
- Clear information architecture
- Search intent coverage
- Unique point of view
- Internal links and metadata
- Claim safety

### `competitive-intel`

Use for competitor teardowns, market maps, positioning briefs, and opportunity
scans.

Research lanes:
- Competitor messaging and offers
- Pricing, funnel, and proof points where public
- SEO/ad footprint
- Differentiation gaps
- Threats and opportunities

Eval gates:
- Sources cited
- Competitors compared consistently
- Opportunities are actionable
- Claims avoid speculation or mark it clearly

## Stop Conditions

Stop and report a blocker when any condition fires:

- Two polish loops produce no measurable improvement.
- A required evidence source is unavailable.
- An eval gate fails for a reason outside the approved scope.
- A launch, merge, legal, or brand approval gate requires a human decision.
- A material claim cannot be substantiated.
- Tooling or credentials fail in a way that prevents verification.

## Evidence Standard

Every completed run should report:

- Archetype and execution mode
- Research sources and VMC report references, if used
- Output files or artifact locations
- Eval gates run and results
- Changes made, if any
- Residual risks and next recommended action

## References

- For detailed archetype schemas and rubrics, read `reference.md`.
- For example run patterns, read `examples.md`.
