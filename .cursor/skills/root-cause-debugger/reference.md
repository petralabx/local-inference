# Root Cause Debugger Reference

This file contains the detailed workflow behind `SKILL.md`. Use it when the bug is non-trivial, cross-domain, reliability-sensitive, or vague.

## 1. Intake Contract

Capture this before searching broadly:

- Symptom: observed behavior in the user's words.
- Expected behavior: what "working" means.
- Environment: local, staging, CI, browser, MCP, DB, external service.
- Domain: one or more taxonomy labels.
- Reproduction target: command, API call, browser path, or log source.
- Known recent changes: only if provided or visible from git history.
- Risk level: low, medium, high, critical.

If the user is vague, infer a default reproduction path and proceed. Ask only if the missing detail blocks all reproduction.

## 2. Failure Taxonomy

Use the first matching category, then add domain tags:

| Category | Primary evidence | First move |
|---|---|---|
| `compile/typecheck` | TypeScript, build, import, module errors | Run or inspect the narrow type/build command |
| `lint` | ESLint or formatter failure | Run or inspect the narrow lint command |
| `unit` | Isolated test failure | Run the specific test file |
| `contract` | Route/domain contract failure | Run the specific contract test |
| `e2e/browser` | Broken user flow or visual/UI failure | Use browser snapshot, console, network, and targeted E2E |
| `api` | HTTP error, bad shape, timeout | Trace route -> validation -> store/service -> dependency |
| `db` | Missing rows, schema mismatch, bad query | Use staging guard before any DB access |
| `external-integration` | SharePoint, DocuSign, email, AI provider, broker, MCP | Read tool/API docs/schema, call read-only health checks first |
| `ci-only` | Failure only in CI | Compare local env, lockfiles, versions, paths, secrets, and timing |
| `performance` | Slow page/API/job | Measure first; use browser CPU profile or timed command |
| `flaky/race` | Intermittent failure | Re-run, isolate nondeterminism, inspect timers, retries, caches, async state |

Domain tags: `chat`, `todos`, `trading`, `swarm-dispatch`, `second-brain`, `projects`, `email`, `memory`, `mcp`.

## 3. Evidence Requirements

At least one of these must exist before editing:

- Failing test with command and failure output.
- Browser snapshot plus console or network evidence.
- API request/response showing wrong status or shape.
- Stack trace with file/function path.
- DB query result showing missing or invalid state.
- CI log pointing to a reproducible command.
- Existing code path proof that a state transition is impossible.

For reliability work, prefer two evidence types: one reproduces the symptom, one localizes the cause.

## 4. Hypothesis Ledger

Keep 1-3 active hypotheses:

```text
Hypothesis:
Expected evidence if true:
Check performed:
Observed evidence:
Status: active | confirmed | disproved | blocked
```

Rules:

- Do not keep more than three active hypotheses.
- Discard a hypothesis after two focused searches with no supporting evidence.
- If all hypotheses fail, re-run intake and choose a new reproduction path.
- Do not make a fix for a hypothesis that is only plausible. Confirm or create a test that exposes it.

## 5. Minimal Fix Gate

Before editing, write a short fix gate:

```text
Root cause:
Minimal files:
Behavioral invariant:
Regression proof:
Rollback:
```

The fix should touch the smallest ownership boundary that actually owns the behavior. If hidden coupling requires wider edits, document why before modifying.

## 6. Verification Matrix

Pick the narrowest check that proves the fix, then run the wider gate for the changed surface.

| Change surface | Narrow check | Wider gate |
|---|---|---|
| VMC route contract | `npx tsx --test src/lib/vmc/__tests__/routes/<file>.test.ts` from `apps/vmc-web` | `npm run test:contracts --prefix apps/vmc-web` |
| VMC lib/store | Specific unit or contract test | `npm run test --prefix apps/vmc-web` and `npm run typecheck --prefix apps/vmc-web` |
| VMC UI | Targeted Playwright spec or browser validation | `npm run typecheck --prefix apps/vmc-web` and `npm run test:e2e:smoke --prefix apps/vmc-web` |
| Cross-domain behavior | Matching `cross-domain/*.test.ts` | `npm run test --prefix apps/vmc-web` |
| Trading v2 | Specific trading contract or Python test | `npm run trading-v2:readiness --prefix apps/vmc-web` plus relevant TS/Python tests |
| CI failure | Reproduce failing CI command locally | `./scripts/ci-local.sh --quick` or full `./scripts/ci-local.sh` |
| Browser-only bug | Snapshot, console, network, screenshot | Targeted E2E or manual browser evidence after fix |
| DB/external issue | Read-only health/query after staging guard | Integration-specific contract or smoke check |

If `node_modules` or local dependencies are missing, report that as environment evidence and install only when the user/task permits. Do not treat missing tools as proof of app behavior.

## 7. Browser Discipline

When using browser tools:

1. List tabs first.
2. Snapshot before structural interaction.
3. Interact by refs from the latest snapshot.
4. After click/fill/type/scroll/navigation, snapshot again.
5. Inspect console and network when a UI action fails silently.
6. Stop after four failed attempts without new evidence.

For visual assertions, use screenshots. For performance, use CPU profile start/stop and read the raw profile plus summary.

## 8. MCP and External Systems

Before every `CallMcpTool`:

1. Read the tool descriptor JSON from the MCP filesystem.
2. Confirm required parameters and allowed values.
3. Call the tool with explicit arguments.
4. Record the evidence in the report.

For VMC MCP flows, prefer:

- `vmc_get_context` before implementation decisions.
- `vmc_report_progress` at major verified checkpoints.
- `vmc_get_repo_health` and `vmc_get_dependency_risks` before merge readiness.
- `vmc_complete_task` only after verification evidence exists.

If descriptor/runtime mismatch or auth failure appears, treat it as a governance blocker and continue non-blocked local verification.

## 9. Staging and Safety

Before DB-affecting operations:

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
```

Never use production resources unless explicitly approved. For Trading, default to paper/staging-only. Do not trigger live trades, irreversible broker actions, destructive migrations, or production deploys from this skill.

## 10. Stop and Escalate

Stop and report a blocker when:

- The symptom cannot be reproduced after three distinct paths.
- The root cause crosses more than three critical modules.
- The task requires production-only access.
- Tooling or credentials are unavailable and no safe fallback exists.
- Fixing would require a product/architecture decision rather than a bug fix.

Blocker report format:

```text
Current target:
Evidence gathered:
What failed:
Why blocked:
Likely next step:
Operator decision needed:
```

## 11. Final Report

Keep the user-facing final concise, but include proof:

```text
Symptom:
Root cause:
Evidence:
Fix:
Verification:
Residual risk:
Follow-up:
```

Include exact command names and whether they passed. If a check was not run, say why.
