# Project Researcher — Reference

Detailed contracts loaded from [SKILL.md](SKILL.md): rubric, convergence loop,
schema details, and stop-condition evidence.

## 1) Rubric (0-100)

Score every iteration against all dimensions:

| Dimension | Weight | Pass expectation |
|---|---:|---|
| Mission + constraints coverage | 15 | Mission, constraints, and non-goals are explicit and accurate |
| Internal findings quality | 20 | Evidence-grounded map of current codebase patterns and boundaries |
| External findings quality | 15 | Credible references with practical guidance (not generic summary) |
| Candidate approaches quality | 25 | At least 2 options, each with pros/cons/risk/effort/blast-radius |
| Recommendation quality | 15 | Clear decision rationale tied to evidence and constraints |
| Contradictions + open questions | 5 | Conflicts resolved or explicitly bounded |
| Source traceability | 5 | Claims map to sources and internal evidence |

Total = 100.

### Pass threshold
- **Pass**: score >= 85
- **Conditional**: 75-84 (iterate unless fixpoint and user accepts risk)
- **Fail**: < 75

## 2) Scoring Math and Control Arm

For each iteration `i`:

1. `score_i = sum(weighted rubric dimensions)`
2. Run control arm by re-scoring unchanged prior brief:
   - `control_i = score(previous_brief_unchanged)`
3. Compute net improvement:
   - `delta_i = score_i - score_(i-1)`
   - `variance_i = abs(control_i - score_(i-1))`
   - treat improvement as material only if `delta_i > variance_i`

This reduces false gains from scorer drift.

## 3) Convergence and Stops

### Convergence (must satisfy both)
1. Rubric pass threshold reached (`score_i >= 85`)
2. Latest iteration adds **no new material findings** versus prior iteration
   (fixpoint: no new constraints, no new external pattern, no new risk class, no
   recommendation change)

### Hard stops
- `max_iterations_reached`: default max `N=5`
- `no_progress`: two consecutive iterations with no material improvement
- `oscillation`: recommendation flips across iterations (A -> B -> A)
- `evidence_gap`: recommendation relies on uncited claims

When a stop fires, halt and report. Do not loop forever.

### Stop-condition evidence format

When halting, include this in `.orchestrator/<slug>/BLOCKER.md`:

```yaml
stop_reason: no_progress
iteration: 4
score_current: 82
score_previous: 81
control_variance: 2
new_material_findings: 0
recommendation_history:
  - Iteration 2: Approach 2
  - Iteration 3: Approach 2
  - Iteration 4: Approach 2
next_action: "Request constraint clarification or accept conditional brief"
```

## 4) `RESEARCH.md` Schema (detailed)

Path: `.orchestrator/<slug>/RESEARCH.md`

### Frontmatter

```yaml
---
slug: <project-slug>
created: <ISO-8601 timestamp>
status: draft | converged | blocked
rubric_score: <0-100>
---
```

### Required sections

```markdown
## Mission and Context
## Internal Findings
## External Findings
## Candidate Approaches
## Recommendation
## Open Questions
## Sources
```

### Candidate approach template (repeat for each approach)

```markdown
### Approach <n> - <title>
- Pros: <benefits>
- Cons: <downsides>
- Risk: <low|medium|high + rationale>
- Effort: <S|M|L or person-days>
- Blast Radius: <modules/routes/systems likely impacted>
```

Minimum: 2 approaches. Preferred: 3.

### Recommendation template

```markdown
## Recommendation
Chosen approach: <Approach n - title>

Why this wins:
- <constraint/evidence linked rationale>
- <trade-off acknowledgment>

What could change this decision:
- <specific unresolved dependency or unknown>
```

### Sources format

Include both internal and external evidence:

```markdown
## Sources
- Internal: `path/to/file` (what it proved)
- Internal: `path/to/another-file` (constraint observed)
- External: https://example.com/article (pattern or caveat)
- External: https://example.com/docs (API or architecture reference)
```

## 5) Validation

Run before handoff:

```bash
bash .cursor/skills/project-researcher/scripts/research-validate.sh .orchestrator/<slug>/RESEARCH.md
```

Expected result:
- Exit `0` when schema is valid
- Exit `1` when schema is invalid (with explicit failure messages)

## 6) Edge-3 Re-Research Intake

When hardening escalates beyond-spec findings:

1. read escalation payload (`BLOCKER.md`, failed commands, attempted fix notes)
2. isolate unresolved design/research question
3. run a focused research loop against that question
4. issue refreshed `.orchestrator/<slug>/RESEARCH.md` for orchestrator re-spec

Escalation intake is mandatory before broadening scope in hardening.

## 7) See Also

- [orchestration-kernel](../orchestration-kernel/SKILL.md) — shared spine contract
- [project-orchestrator](../project-orchestrator/SKILL.md) — downstream spec/build spine
- [project-hardener](../project-hardener/SKILL.md) — escalation source for re-research
