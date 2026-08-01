---
slug: sample-reliable-project-pipeline
created: 2026-06-15T10:15:00-04:00
status: converged
rubric_score: 89
---

## Mission and Context
Build a reusable project-research skill that produces a structured pre-spec brief.
The brief must feed orchestrator planning without changing orchestrator behavior
when no research artifact exists.

## Internal Findings
- Existing orchestration standards require first-class skill frontmatter, role-based
  model language, and scripts with clear validation outcomes.
- `project-orchestrator` already has Stage 1 spec generation and should only gain a
  conditional read path for `.orchestrator/<slug>/RESEARCH.md`.
- Validation patterns in sibling scripts favor simple shell + awk checks with clear
  pass/fail output.

## External Findings
- Structured pre-build research briefs reduce planning drift when they force explicit
  trade-offs and risk articulation.
- Quality loops are more stable when recommendation scoring includes a control arm to
  estimate scorer variance before accepting improvements.
- Convergence criteria should combine threshold quality and a no-new-findings fixpoint
  to avoid endless revision churn.

## Candidate Approaches
### Approach 1 - Internal-only mapping
- Pros: Fast and low overhead; uses only repository evidence.
- Cons: Misses external best-practice patterns and emerging trade-offs.
- Risk: Medium; recommendation quality can be stale for new problem spaces.
- Effort: S
- Blast Radius: Low; touches skill docs only.

### Approach 2 - External-only benchmarking
- Pros: Surfaces modern approaches quickly.
- Cons: Ignores local constraints and existing architecture boundaries.
- Risk: High; recommendations may be mismatched to repository reality.
- Effort: M
- Blast Radius: Medium; can mis-seed later spec decisions.

### Approach 3 - Combined internal + external looped synthesis
- Pros: Balances local constraints with best-practice options; supports stronger recommendations.
- Cons: Slightly more process overhead and scoring discipline required.
- Risk: Low; evidence is triangulated and contradiction handling is explicit.
- Effort: M
- Blast Radius: Low to Medium; primarily documentation and orchestration handoff behavior.

## Recommendation
Chosen approach: Approach 3 - Combined internal + external looped synthesis

Why this wins:
- It preserves repository alignment by anchoring findings in internal evidence.
- It upgrades option quality through external references and contradiction checks.
- It supports deterministic handoff quality using rubric scoring plus control-arm variance checks.

What could change this decision:
- If the project is purely local and time-critical, Approach 1 may be acceptable as a constrained mode.

## Open Questions
- Should a future version of the validator enforce source category minimums (for example, at least one internal and one external source)?
- Should oscillation detection be configurable per project, or fixed in the skill reference?

## Sources
- Internal: `.cursor/skills/README.md` (authoring bar and orchestration pipeline intent)
- Internal: `.cursor/skills/project-orchestrator/SKILL.md` (Stage 1 behavior and lifecycle)
- Internal: `.cursor/skills/project-orchestrator/scripts/spec-validate.sh` (script validation style)
- External: https://martinfowler.com/articles/ (architecture trade-off documentation patterns)
- External: https://www.thoughtworks.com/radar (technology risk framing examples)
