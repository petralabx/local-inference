---
name: project-research-runner
description: Converts a project intake or draft into a research-backed plan, roadmap, milestones, risks, and tasks. Use when the user wants a Cursor-executed research run for a website, skill, workflow, integration, business project, utility, or system build, especially when the result should include a builder-compatible draft update.
---

# Project Research Runner

Use this skill to execute a Project Builder-style research run from Cursor. Treat
it as a generic version of: classify project → frame draft → run empirical
research → synthesize a builder-compatible update → hand back evidence for
review.

## When To Use

- The user mentions Project Builder, Run Research, Karpathy-style research,
  builder draft refinement, or a Cursor Skill pilot.
- The user wants a `Skill`, `Workflow`, `Integration`, `System Build`,
  `Business Project`, or `Utility` researched before implementation.
- The desired output is a better draft, implementation plan, portal PR plan,
  skill spec, workflow design, or research-backed roadmap.

## Default Mode

Default to `report-only`: research and synthesize, but do not edit code unless
the user explicitly asks for implementation or approves a plan.

If implementation is approved inside a product repo, follow that repo's local
branch, verification, and documentation rules.

## Intake Classification

Start every run by extracting or asking for the missing fields:

```text
Project Research Intake
- Project name:
- Project type: System Build | Business Project | Utility
- Target system: VMC | SWARM | PLX Portal | Multiple | Other
- Primary outcome: Skill | Workflow | Integration | Enhancement | Presentation | Analysis | Report | Tracker | Research Brief
- Output style: Executive | Operational | Technical
- Current draft or problem statement:
- Constraints and non-goals:
- Human approval needed before edits? yes/no
```

If the user has already provided screenshots or a draft, infer the classification
from that material and state assumptions briefly.

## Research Loop

Follow this checklist:

```text
Project Research Progress
- [ ] 1) Confirm classification and mode
- [ ] 2) Freeze the current draft/problem statement
- [ ] 3) Run a divergence pass when the problem has multiple plausible paths
- [ ] 4) Identify research lanes and success gates
- [ ] 5) Gather evidence from repo context, docs, web/source research, and user material
- [ ] 6) Synthesize findings into builder draft sections
- [ ] 7) Emit a `json-draft-update` block when the result should feed Project Builder
- [ ] 8) Evaluate against quality gates
- [ ] 9) Handoff evidence, risks, and next actions
```

Research should be empirical and concrete: look for existing repo capabilities,
prior art, constraints, user-facing UX, API boundaries, documentation impact, and
integration risks before proposing new work.

## Divergence Pass

Use a Verbalized Sampling-style pass when the project could collapse into the
most typical plan too early: new products, websites, architecture choices,
skills, workflows, integrations, naming, positioning, or anything with multiple
credible approaches.

Prompt yourself to generate 5 candidate approaches with rough probabilities:

```text
Generate 5 meaningfully different approaches with rough probabilities.
Include:
- One conservative/reuse-first approach
- One ambitious/high-upside approach
- One integration-first approach
- One UX/operator-first approach
- One contrarian or least-obvious approach

For each:
- Probability this is the best path:
- Why it might win:
- Why it might fail:
- Evidence needed:
- What to preserve even if this path is not chosen:
```

Do not average the candidates into a bland plan. Carry forward the strongest
specific ideas, including lower-probability options when they expose a real risk,
better user experience, or asymmetric upside.

## Builder-Compatible Output

For a Project Builder draft update, include these sections:

- `Summary`
- `Architecture` or `System Design`, with Mermaid when useful
- `Recommendations`
- `Open Questions`
- `Roadmap`
- `Milestones`
- `Risks`
- `Tasks` or `Agent Task Plan`
- `Evidence`
- `Residual Risks`

Also include this fenced block when the output should be parsed back into a
builder-style draft:

```json-draft-update
{
  "summary": "Concise updated project summary.",
  "recommendations": [
    "Specific recommendation grounded in research."
  ],
  "roadmap": [
    {
      "id": "phase-1",
      "name": "Phase name",
      "description": "What happens in this phase.",
      "order": 1,
      "estimatedDays": 3,
      "dependencies": []
    }
  ],
  "milestoneRegister": [
    {
      "id": "ms-1",
      "name": "Milestone name",
      "description": "Observable completion condition.",
      "status": "pending",
      "phaseId": "phase-1"
    }
  ],
  "riskRegister": [
    {
      "id": "risk-1",
      "description": "Risk statement.",
      "likelihood": "medium",
      "impact": "medium",
      "mitigation": "Mitigation plan.",
      "owner": "recommended owner"
    }
  ],
  "agentTaskPlan": [
    {
      "id": "task-1",
      "title": "Task title",
      "description": "Task description and acceptance criteria.",
      "todoType": "task",
      "priority": "medium",
      "assignedAgent": "recommended agent or team",
      "phaseId": "phase-1",
      "estimatedHours": 2
    }
  ]
}
```

Use only these enum values:

- `status`: `pending`, `in-progress`, `completed`
- `likelihood` and `impact`: `low`, `medium`, `high`
- `todoType`: `epic`, `story`, `task`, `subtask`
- `priority`: `low`, `medium`, `high`, `urgent`

## Quality Gates

A research run is not done until it checks:

- Existing capability reuse: no duplicate feature, skill, workflow, or API is
  proposed without checking for an owner first.
- Diversity check: when a divergence pass was warranted, the output preserves
  at least one non-obvious option, risk, or design move instead of only the most
  typical answer.
- Builder completeness: summary, recommendations, roadmap, milestones, risks,
  and tasks are populated.
- Repo boundary: product UI and business workflows stay in the product repo;
  agent skills, orchestration, and runtime automation stay in the agent/control
  repo unless a clear integration contract is needed.
- Claim safety: business, legal, SEO, and capability claims are sourced or
  labeled as assumptions.
- Pilot handoff: output tells the user exactly what to try next and what
  evidence proves the pilot worked.

## Handoff Format

End with:

```text
Pilot Handoff
- Mode:
- Classification:
- Divergence pass used: yes/no
- Output produced:
- Evidence checked:
- Builder JSON included: yes/no
- Recommended pilot steps:
- Blockers or risks:
```

Keep the handoff concise. If code edits were made, include files changed and
verification commands run. If no edits were made, say so explicitly.
