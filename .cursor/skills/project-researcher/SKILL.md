---
name: project-researcher
description: Build a pre-spec research brief by combining internal repo mapping with external best-practice research, then iterating in an objective loop until brief quality converges. Use when the user says "research this", "scope options before building", "what are the approaches", "investigate before planning", or asks for a recommendation with trade-offs.
---

# Project Researcher

Turn a project request into a high-confidence `RESEARCH.md` handoff before
spec/planning. This skill combines internal repo evidence and external
best-practice research, then runs a bounded scoring loop until quality reaches a
fixpoint.

## When to Use
- The user asks for pre-build scoping, options, trade-offs, or a recommendation.
- Trigger phrases include: "research this", "scope options before building",
  "what are the approaches", "investigate before planning".
- A project needs a documented brief at `.orchestrator/<slug>/RESEARCH.md` before
  `project-orchestrator` Stage 1.

## When NOT to Use
- The user wants immediate implementation for a small/local change.
- The task is pure debugging/root cause (use `codebase-investigation`).
- The task already has an approved spec and is ready for build execution.

## Lifecycle

```text
Project Researcher — <slug>
- [ ] 0) Frame mission + constraints (optionally via pre-plan-recalibrator)
- [ ] 1) Map internal repo reality (codebase-investigation evidence)
- [ ] 2) Gather external references (WebSearch/WebFetch)
- [ ] 3) Draft RESEARCH.md v1 (schema-complete)
- [ ] 4) Score against rubric (0-100)
- [ ] 5) Run control arm (re-score prior unchanged brief)
- [ ] 6) Decide converge vs iterate (fixpoint + stop guards)
```

### 0) Frame mission and scope
Capture mission, constraints, non-goals, and intended users. If intent is fuzzy,
run `pre-plan-recalibrator` first.

### 1) Internal mapping (required)
Use `codebase-investigation` to map current architecture and constraints:
- entry points, key modules, ownership boundaries
- existing patterns to reuse
- integration risks and blast-radius boundaries

Record findings in `## Internal Findings`.

### 2) External research (required)
Use `WebSearch` to find credible references and `WebFetch` to extract concrete
guidance. Record practical patterns, caveats, and contradictory advice.

Record findings in `## External Findings`.

### 3) Draft the brief
Write `.orchestrator/<slug>/RESEARCH.md` using this required schema:
- Frontmatter: `slug`, `created`, `status`, `rubric_score`
- Sections: `Mission and Context`, `Internal Findings`, `External Findings`,
  `Candidate Approaches`, `Recommendation`, `Open Questions`, `Sources`

Candidate approaches must include at least 2 options (prefer 3), each with:
pros, cons, risk, effort, and blast-radius.

### 4) Score quality (rubric)
Score the brief using the rubric in [reference.md](reference.md):
- coverage of internal constraints
- quality and relevance of external evidence
- quality of candidate approaches and trade-offs
- recommendation strength and contradiction handling
- source traceability

### 5) Control arm (null baseline)
Re-score one unchanged prior brief (or the previous iteration) in parallel to
estimate scorer variance. Use that variance to avoid false "improvements."

### 6) Convergence logic
Continue iterating only when new material findings exist and rubric quality has
not converged.

Converged when both are true:
1. Rubric passes threshold.
2. Latest iteration adds no new material findings (fixpoint).

Hard stops (halt and report, never infinite loop):
- max iterations reached
- no-progress/oscillation detector fires
- missing evidence or unresolved contradictions block recommendation quality

On hard stop, write `.orchestrator/<slug>/BLOCKER.md` with evidence and next
action.

## RESEARCH.md Handoff
`project-orchestrator` Stage 1 consumes `.orchestrator/<slug>/RESEARCH.md` when
present to seed candidate trade-offs and recommendation into `SPEC.md`; when
absent, orchestration follows its existing behavior.

## Escalation Intake (Edge 3 return path)

`project-hardener` may escalate back for re-research when an out-of-spec design
finding needs new discovery, not just re-implementation. Intake contract:

1. consume escalation evidence from hardener (finding, failed attempts, blocker)
2. focus research on the unresolved design question
3. emit an updated `RESEARCH.md` for `project-orchestrator` re-spec approval

This keeps hardening bounded and closes the researcher -> orchestrator ->
hardener -> researcher/orchestrator loop.

Validate a brief before handoff:

```bash
bash .cursor/skills/project-researcher/scripts/research-validate.sh .orchestrator/<slug>/RESEARCH.md
```

## Model Roles (runtime-resolved)

Use role names, not hardcoded model IDs:
- **deep**: synthesis, rubric scoring, contradiction resolution
- **mechanical**: repository mapping, section formatting, schema checks
- **critic**: independent challenge pass on recommendation and risks

## Additional Resources
- Shared spine contract: [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Rubric, scoring math, stop evidence format: [reference.md](reference.md)
- Brief schema example: [examples/RESEARCH.sample.md](examples/RESEARCH.sample.md)
- Brief validator: [scripts/research-validate.sh](scripts/research-validate.sh)
- Internal mapping method: [codebase-investigation](../codebase-investigation/SKILL.md)
- Intent calibration: [pre-plan-recalibrator](../pre-plan-recalibrator/SKILL.md)
