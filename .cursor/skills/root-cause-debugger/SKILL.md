---
name: root-cause-debugger
description: Diagnoses and fixes codebase bugs through reproducible evidence, lifecycle tracing, hypothesis ledgers, minimal scoped fixes, and verification gates. Use when the user reports failing tests, broken UI flows, unreliable chat/swarm behavior, API errors, CI failures, flaky behavior, DB issues, external integration failures, performance regressions, or asks to debug/root-cause/fix an unknown issue.
---

# Root Cause Debugger

Use this skill when the user gives a bug report and expects the agent to find the cause, fix it, and prove the fix. It is global and repo-aware: apply the generic debugging contract everywhere, and use the VMC playbooks when working in agent-swarm/VMC repos.

## Operating Contract

Do not edit code until there is reproduction evidence. Evidence can be a failing test, command output, stack trace, browser snapshot, console/network log, API response, DB query result, or CI log.

Before editing, state:

1. Symptom classification.
2. Reproduction evidence.
3. Most likely root cause or active hypotheses.
4. Files likely touched.
5. Minimal fix plan.
6. Verification commands or browser/API checks that will prove the fix.

If a bug needs code changes, read and follow `autonomous-verifier`. If a new contract invariant is needed before implementation, read and follow `reliable-tdd-loop`. If the issue is a PR/CI correction loop, use `babysit`.

## Failure Taxonomy

Classify the bug before broad searching:

- `compile/typecheck`
- `lint`
- `unit`
- `contract`
- `e2e/browser`
- `api`
- `db`
- `external-integration`
- `ci-only`
- `performance`
- `flaky/race`
- `chat`
- `todos`
- `trading`
- `swarm-dispatch`

## Workflow

1. Intake: restate observed behavior, expected behavior, environment, suspected domain, and confidence.
2. Reproduce: run the narrowest relevant test or browser/API flow first.
3. Localize: trace from entry point to store/service/DB/external dependency/callback/render path.
4. Hypothesize: keep 1-3 hypotheses with proof/disproof evidence. Drop hypotheses after two searches with no evidence.
5. Fix: apply the smallest scoped change that addresses the proven cause.
6. Verify: rerun the narrow repro, then the relevant wider gate.
7. Report: include symptom, root cause, evidence, fix summary, verification, residual risk, and follow-up.

## VMC Quick Routing

When the repo contains `apps/vmc-web`, read [domain-playbooks.md](domain-playbooks.md) and use the matching lifecycle:

- Chat issues: UI input -> chat stream route -> chat dispatch -> swarm queue -> callback/completion -> persistence -> UI render.
- To-Dos issues: API/stream -> store -> dispatch/steer -> cron/maintenance -> reconciliation -> UI state.
- Trading issues: UI/API -> trading-v2 store/riskguard -> paper pipeline -> readiness/KPI -> promotion gates.
- Swarm issues: enqueue/dispatch -> queue store -> worker/adapter -> callback -> dispatch poll -> stream/UI.

Use [reference.md](reference.md) for command selection, MCP/browser/staging rules, and stop conditions.

## Verification Gates

Run the narrow failing check first. For VMC work, common gates are:

- `npx tsx --test <specific-test>` from `apps/vmc-web`.
- `npm run test:contracts --prefix apps/vmc-web`.
- `npm run test --prefix apps/vmc-web`.
- `npm run typecheck --prefix apps/vmc-web`.
- `npm run test:e2e:smoke --prefix apps/vmc-web` for changed UI flows.
- `npm run trading-v2:readiness --prefix apps/vmc-web` for Trading v2 readiness changes.
- `./scripts/ci-local.sh --quick` or `./scripts/ci-local.sh` for cross-stack changes.

Before DB-affecting operations, source staging secrets and run the repo's staging guard. Never use production resources unless explicitly approved.

## Required Output

Use this final report shape:

```text
Symptom:
Root cause:
Evidence:
Fix:
Verification:
Residual risk:
Follow-up:
```

For detailed templates and examples, read [templates.md](templates.md) and [examples.md](examples.md). For invocation and rollout guidance, read [rollout.md](rollout.md).

## Stop Conditions

Stop and report a blocker when:

- The bug cannot be reproduced after three distinct evidence-gathering attempts.
- Browser interaction fails four times without new evidence.
- Required credentials, services, dependencies, or staging guard checks are unavailable.
- The fix would touch more than three critical modules without operator approval.
- Production resources would be required.

## Anti-Patterns

- Guessing from code shape without reproduced evidence.
- Broad refactors during a bug fix.
- Adding permanent noisy logs instead of targeted instrumentation or tests.
- Declaring success after only one weak check.
- Hiding CI, test, or browser failures as "probably unrelated" without evidence.
- Calling VMC MCP tools without reading the schema descriptor first.
