---
name: pre-plan-recalibrator
description: Pauses before implementation planning to clarify user intent, context, constraints, success criteria, risks, and task framing. Use when explicitly invoked for prompt calibration, pre-plan recalibration, or planning prep. The agent may recommend it only when a plan would otherwise be materially under-specified or risky.
---

# Pre-Plan Recalibrator

Use this skill as a structured pause after discussion and before writing an implementation plan. Its job is to turn fuzzy deliberation into a crisp planning brief.

Do not use this skill for simple edits, direct answers, or cases where the user clearly says to skip questions. If you auto-recommend it, explain the risk in one sentence and ask whether to run a quick calibration.

## Operating Contract

1. Review the conversation and available context first.
2. Ask only unanswered questions that materially change the plan.
3. Prefer 5-8 grouped questions for standard use.
4. Skip any question the agent can answer by reading files, docs, tests, or prior messages.
5. Do not write the implementation plan yet.
6. After answers, produce a Calibration Brief and wait for user approval before planning.

If the user explicitly invokes the skill, run it. If the agent thinks it is necessary but the user did not invoke it, ask:

```text
I recommend a quick pre-plan calibration because <specific risk>. Want me to ask the calibration questions before I write the plan?
```

## Question Selection

Ask from these groups. Combine related items and omit anything already clear.

### 1. Intent And Outcome

- What outcome are we optimizing for?
- What should be true when this is done?
- Is the priority speed, reliability, UX, maintainability, cost, or learning?

Skip when the user already gave a concrete deliverable and success state.

### 2. Context And Source Of Truth

- Which files, docs, prior decisions, examples, users, or workflows should anchor this?
- Is there an existing pattern we should follow?
- Is any current behavior canonical even if it looks imperfect?

Skip when the agent can inspect the repo or the context is explicit.

### 3. Scope And Non-Goals

- What must stay out of scope?
- What existing behavior must not change?
- Should this be a surgical change, a refactor, or a new capability?

Skip for tiny local fixes.

### 4. Constraints

- Any constraints on architecture, dependencies, style, time, compatibility, security, deployment, or data handling?
- Are there hard rules from the repo, product, customer, or operating environment?

Skip when repo rules and local patterns already answer this.

### 5. Success Criteria And Verification

- How should we verify success?
- Which tests, checks, screenshots, API responses, metrics, acceptance criteria, or review gates matter?
- What would make the plan unacceptable?

Usually ask this unless verification is obvious.

### 6. Risk And Reversibility

- Does this touch production, data, auth, migrations, payments, external systems, user-visible UI, or irreversible operations?
- How reversible should the approach be?
- What failure mode worries you most?

Skip for answer-only, docs-only, or harmless local work.

### 7. Examples And Counterexamples

- Do you have an example of the desired result?
- Do you have an example of what not to do?
- Are there previous attempts, rejected approaches, or style references?

Ask when taste, format, UX, tone, or ambiguous behavior matters.

### 8. Plan Shape Preferences

- Do you want alternatives and trade-offs, or a direct recommended plan?
- How detailed should the plan be?
- Should the plan include checkpoints, test gates, rollout steps, or owner decisions?

Skip when the user requested a specific plan format.

## Default Question Batch

When no better custom batch is obvious, ask:

```text
Before I write the plan, a quick calibration:

1. What outcome are we optimizing for, and what should be true when this is done?
2. What source of truth should anchor the plan: files, docs, examples, prior decisions, or existing workflows?
3. What is explicitly out of scope, and what current behavior must not change?
4. What constraints matter: dependencies, architecture, security, compatibility, deployment, time, or data handling?
5. How should we verify success?
6. What are the biggest risks or failure modes to avoid?
7. Do you want a direct plan, alternatives with trade-offs, or a staged plan with approval checkpoints?
```

## Calibration Brief

After the user answers, produce this brief and stop for approval:

```text
Calibration Brief

Restated task:
<one clear sentence>

Context to use:
<files, docs, examples, prior decisions, constraints>

Assumptions:
<only unresolved assumptions that affect the plan>

Non-goals:
<what will not be included>

Success criteria:
<acceptance checks and verification>

Plan implications:
<what the implementation plan must account for>

Remaining questions:
<blockers only, otherwise "No blockers to planning.">

Approve this brief for planning, or adjust anything?
```

Only after approval should the agent write the implementation plan.

## Technique Guidance

- Treat prompt engineering as context design, workflow design, and evaluation design.
- Use few-shot examples when format, tone, or behavior is hard to describe abstractly.
- Use staged planning when the task has meaningful risk, unknowns, or external dependencies.
- Use explicit output contracts for every plan.
- Avoid requesting or exposing hidden chain-of-thought. Ask for summaries, assumptions, trade-offs, and verification instead.

For source-grounded notes and technique mappings, read [reference.md](reference.md) only when needed.

## Anti-Patterns

- Asking a long questionnaire for simple tasks.
- Re-asking details already present in the conversation.
- Planning before success criteria are clear on ambiguous work.
- Treating prompt engineering as magic wording.
- Expanding scope under the banner of better context.
- Overriding a user instruction to proceed unless there is a material risk.
- Producing the implementation plan before the Calibration Brief is approved.
