---
name: kap
description: Evaluates whether an implementation plan is 100% ready to execute. Use when the user invokes /kap or asks if a plan is ready, production-ready, execution-ready, or safe to start. Produces a conservative readiness verdict, blockers, concrete execution checklist, and PR slicing guidance.
disable-model-invocation: true
---

# KAP Plan Readiness Gate

## Invocation

Use this skill when the user explicitly invokes `/kap` or asks whether a plan is ready to execute.

Default stance: a plan is **not ready** until scope, ownership, data safety, tests, rollback, sequencing, and verification are explicit.

## Core Question

Answer:

> Is this plan 100% ready to execute?

Do not answer "yes" unless every readiness gate below passes. If any gate is unclear, answer "No" or "Not yet" and list the exact missing decisions.

## Readiness Gates

Check the plan for:

1. Scope lock: files, modules, and non-goals are explicit.
2. Ownership: each work package has a clear owner or implementation lane.
3. Data safety: migrations, tenant boundaries, idempotency, and destructive-operation risks are handled.
4. Test strategy: unit, contract, fixture/integration, browser, and regression tests are named.
5. Verification commands: exact commands are listed and appropriate for the changed surfaces.
6. Rollback: migration and feature rollback are described where relevant.
7. Sequencing: high-risk work is ordered after safety gates, or split into smaller PRs.
8. Blast radius: critical modules, API routes, and background jobs are identified.
9. Observability: success/failure signals are visible in logs, UI, metrics, or DB records.
10. Stop conditions: clear blockers tell the agent when not to continue.

## Verdict Rubric

- `READY`: all gates pass; execution can start.
- `READY WITH CONSTRAINTS`: execution can start only on a named slice or first PR.
- `NOT READY`: one or more blocking decisions are missing.
- `REJECTED`: the plan violates safety, data, security, or risk rules.

## Required Output Format

Use this structure:

```markdown
## Verdict
<READY | READY WITH CONSTRAINTS | NOT READY | REJECTED>

## Why
<Short evidence-backed explanation.>

## Blocking Gaps
- <Gap 1, or "None">

## Execution Checklist
- <Concrete step 1>
- <Concrete step 2>

## PR Slicing
- PR 1: <scope, files, verification>
- PR 2: <scope, files, verification>

## Verification Gates
- <Command or behavioral proof>

## Stop Conditions
- <When to stop and ask>
```

## Guidance

- Be direct. Do not soften a missing gate.
- Prefer smaller PR slices when the plan touches auth, migrations, execution services, or UI behavior.
- For trading or financial systems, separate signal evidence from execution safety. Never let UI polish outrank risk, idempotency, auditability, and data quality.
- If the user asks to execute a plan that is not ready, recommend the smallest safe first slice.
