# Domain Playbooks

Use these playbooks when the current workspace is VMC/agent-swarm or has an `apps/vmc-web` app. Start with the user's symptom, then trace the full lifecycle until the broken transition is found.

Run these from the active VMC repo root. The paths below are repo-relative so they work across local checkouts and shared development hosts.

## Chat Reliability

Trigger phrases:

- "chat messages never complete"
- "typing into the abyss"
- "swarm never answers"
- "chat stream hangs"
- "messages disappear"

Lifecycle:

```text
UI input -> chat stream API -> dispatch context -> chat dispatch -> swarm queue -> worker/adapter -> callback/completion -> persistence -> UI render
```

Key surfaces:

- `apps/vmc-web/src/components/vmc/chat/`
- `apps/vmc-web/src/app/api/vmc/chat/stream/route.ts`
- `apps/vmc-web/src/lib/vmc/chat/`
- `apps/vmc-web/src/lib/vmc/chat/chat-dispatch.ts`
- `apps/vmc-web/src/lib/vmc/chat/dispatch-context.ts`
- `apps/vmc-web/src/app/api/vmc/queue/dispatch-callback/route.ts`
- `apps/vmc-web/src/lib/vmc/queue/swarm-dispatches.ts`

First checks:

1. Reproduce via browser or the narrow chat contract test.
2. Confirm user message is accepted and persisted.
3. Confirm stream route returns the expected status and event shape.
4. Confirm a dispatch is created with correlation IDs linking chat message/session to swarm job.
5. Confirm callback/completion path can update the original message/thread.
6. Confirm frontend subscribes to the correct stream and renders completion state.

Common root causes:

- Chat route acknowledges input but never creates a dispatch.
- Dispatch exists but lacks correlation data needed by callback.
- Callback writes completion to a different entity than the UI reads.
- Stream handler closes early or swallows errors.
- UI optimistic state never reconciles with persisted completion.
- Race between initial render, stream subscription, and dispatch completion.

Useful tests:

- `apps/vmc-web/src/lib/vmc/__tests__/routes/chat-thread-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/chat-dispatch-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-todos-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-second-brain-contracts.test.ts`
- `apps/vmc-web/e2e/chat-load.spec.ts`

Minimum proof for a fix:

- A failing chat/dispatch contract or browser+network evidence before the fix.
- A passing narrow chat contract after the fix.
- If UI-visible, browser snapshot after sending a message and observing completion or a specific non-silent failure state.

## To-Dos

Trigger phrases:

- "todo did not dispatch"
- "todo stuck"
- "todo status wrong"
- "stale todo"
- "completion callback did not update"

Lifecycle:

```text
API/UI create -> store -> dispatch/steer -> queue/cron -> callback -> status reconciliation -> stream/UI
```

Key surfaces:

- `apps/vmc-web/src/app/api/vmc/todos/route.ts`
- `apps/vmc-web/src/app/api/vmc/todos/stream/route.ts`
- `apps/vmc-web/src/app/api/vmc/todos/[id]/route.ts`
- `apps/vmc-web/src/app/api/vmc/todos/[id]/dispatch/route.ts`
- `apps/vmc-web/src/app/api/vmc/todos/[id]/steer/route.ts`
- `apps/vmc-web/src/app/api/vmc/todos/maintenance/route.ts`
- `apps/vmc-web/src/app/api/cron/todo-dispatch/route.ts`
- `apps/vmc-web/src/lib/vmc/todos.ts`
- `apps/vmc-web/src/lib/vmc/todos-store.ts`
- `apps/vmc-web/src/lib/vmc/todos-dispatch.ts`

First checks:

1. Confirm the todo row/state exists and has the expected status.
2. Confirm dispatch history or queue record was created.
3. Confirm lease/stale fields are not preventing dispatch.
4. Confirm callback can map back to the todo.
5. Confirm stream/API returns updated state.
6. Confirm UI state is not using stale local cache.

Common root causes:

- Todo created without required dispatch metadata.
- Lease field marks a todo as in-progress forever.
- Dispatch cron filters out eligible todos due to bad status or timestamp.
- Callback cannot resolve the todo ID.
- Status reconciliation overwrites a completed state with stale data.

Useful tests:

- `apps/vmc-web/src/lib/vmc/__tests__/routes/todos-route-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/todos-store-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/todo-dispatch-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-todos-contracts.test.ts`
- `apps/vmc-web/e2e/todos-load.spec.ts`

Minimum proof for a fix:

- Contract test proves the todo transition or callback mapping.
- Typecheck passes if route/store types changed.
- Browser or API evidence shows visible status change for user-facing bugs.

## Swarm Dispatch

Trigger phrases:

- "swarm dispatch never completes"
- "agent did not start"
- "dispatch callback missing"
- "royale enqueue failed"
- "worker returned but UI never updated"

Lifecycle:

```text
enqueue -> queue store -> dispatch contract -> worker/adapter -> callback -> poll/stream -> UI or linked domain
```

Key surfaces:

- `apps/vmc-web/src/lib/vmc/dispatch/dispatch-contract.ts`
- `apps/vmc-web/src/lib/vmc/queue/swarm-dispatches.ts`
- `apps/vmc-web/src/lib/vmc/queue/dispatch-links-store.ts`
- `apps/vmc-web/src/lib/vmc/workflows/workflow-dispatch.ts`
- `apps/vmc-web/src/app/api/vmc/workflow-dispatch/route.ts`
- `apps/vmc-web/src/app/api/cron/dispatch-poll/route.ts`
- `apps/vmc-web/src/app/api/vmc/queue/dispatch-callback/route.ts`
- `apps/vmc-web/src/app/api/vmc/royale/dispatch/route.ts`
- `apps/vmc-web/src/app/api/vmc/royale/dispatch/stream/route.ts`
- `apps/vmc-web/src/app/api/vmc/royale/dispatch/enqueue/route.ts`
- `apps/vmc-web/src/lib/vmc/execution/adapters/cos-dispatch-adapter.ts`

First checks:

1. Identify the domain link: chat, todo, workflow, royale, trading, or raw dispatch.
2. Confirm enqueue response includes dispatch ID and correlation link.
3. Confirm queue store has an expected pending/running/completed transition.
4. Confirm adapter or worker receives payload.
5. Confirm callback route validates and persists result.
6. Confirm polling/streaming reads the same dispatch record.

Common root causes:

- Dispatch ID generated but link row missing.
- Callback validates against a stale shape.
- Adapter returns success but callback maps it as failure.
- Poll route filters completed records incorrectly.
- Stream route watches a different dispatch scope than enqueue uses.

Useful tests:

- `apps/vmc-web/src/lib/vmc/__tests__/routes/swarm-dispatches-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/royale-dispatch-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/royale-enqueue-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/dispatcher-health-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/cross-domain/swarm-coordination-contracts.test.ts`
- `apps/vmc-web/e2e/dispatch.spec.ts`
- `apps/vmc-web/e2e/agents.spec.ts`

Minimum proof for a fix:

- Before/after dispatch lifecycle evidence showing the broken transition now completes.
- Contract coverage for callback/link/poll behavior if changed.

## Trading V2

Trigger phrases:

- "trading signal did not execute"
- "paper dispatcher failed"
- "promotion gate wrong"
- "riskguard blocked incorrectly"
- "readiness failing"
- "KPI or regime stale"

Safety rule:

Default to paper/staging-only. Do not trigger live trades, broker actions, irreversible orders, or production resources unless explicitly approved.

Lifecycle:

```text
signal/input -> trading-v2 API -> store/riskguard -> paper dispatcher -> ledger/KPI -> readiness -> promotion gate
```

Key surfaces:

- `apps/vmc-web/src/lib/vmc/trading-v2/`
- `apps/vmc-web/src/app/api/vmc/trading-v2/`
- `apps/vmc-web/src/components/vmc/trading-lab/`
- `scripts/trading-research/`
- `docs/modules/trading-v2/`
- `docs/runbooks/trading-v2-*`

First checks:

1. Confirm whether the issue is TS API/UI, Python pipeline, DB state, or readiness/promotion math.
2. Run or inspect the narrow trading contract/readiness command.
3. Confirm riskguard/circuit breaker did not intentionally block the action.
4. Confirm paper dispatcher wrote the expected ledger entry.
5. Confirm KPI/readiness reads fresh data.
6. Confirm promotion gates use the intended threshold and time window.

Common root causes:

- Stale market data or stale readiness snapshot.
- Riskguard threshold mismatch between API and Python pipeline.
- Paper ledger entry missing required fields.
- Promotion gate reads baseline data instead of current trial data.
- Circuit breaker remains latched after recovery.

Useful checks:

- `npm run trading-v2:readiness --prefix apps/vmc-web`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/trading-paper-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/routes/trading-lab-kpi-m42-contracts.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/trading-v2-promotion-baseline.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/trading-v2-riskguard-breaker.test.ts`
- `apps/vmc-web/src/lib/vmc/__tests__/trading-v2-circuit-breaker-manipulation.test.ts`
- `scripts/trading-research/test_paper_dispatcher_contracts.py`

Minimum proof for a fix:

- Paper/staging evidence only.
- Narrow trading contract or Python test passes.
- Readiness or KPI command passes when the bug affects promotion/readiness.

## API Routes

Lifecycle:

```text
request -> auth/validation -> handler -> store/service -> dependency -> response shape -> caller
```

Checks:

1. Confirm method, route path, status, and response shape.
2. Inspect Zod or input validation before store logic.
3. Trace store/service imports and avoid bypassing established module boundaries.
4. Confirm error path returns the contract shape, not an unhandled exception.
5. Add or update a route contract for new behavior.

Minimum proof:

- Route contract covers happy path, invalid input, and dependency failure when relevant.

## DB and Persistence

Safety:

Run staging guard before any DB-affecting command. Prefer read-only queries for diagnosis.

Checks:

1. Identify the authoritative table/store for the domain.
2. Confirm migrations provide required columns.
3. Compare persisted state to API/store expectations.
4. Check timestamp, lease, status, and correlation ID fields first for workflow bugs.
5. Verify writes and reads use the same key and tenant/scope.

Common root causes:

- Missing migration in the current environment.
- Store writes one shape and API reads another.
- Bad default timestamp/status.
- Correlation ID not persisted across callback boundary.

## Browser and UI

Lifecycle:

```text
user action -> component state -> API/network -> stream/subscription -> cache/reconciliation -> render
```

Checks:

1. Browser snapshot before interaction.
2. Network request and response for the action.
3. Console errors and React warnings.
4. Loading/error/empty states.
5. Stream or polling subscription lifecycle.
6. Stale local state, optimistic update, or cache invalidation.

Minimum proof:

- Fresh snapshot after the fixed action and, when applicable, network/console evidence.

## CI-Only Failures

Checks:

1. Identify exact failing command and job.
2. Re-run the command locally if feasible.
3. Compare Node, npm, Python, env vars, path assumptions, lockfile, and dependency install state.
4. Check tests relying on time, order, network, filesystem, or hidden local state.
5. Avoid "fixing" CI by weakening tests unless the test is proven invalid.

Minimum proof:

- Local reproduction or a clear environment delta plus a verification command that matches CI.

## Flaky or Race Failures

Checks:

1. Re-run the narrow command multiple times only after recording baseline failure.
2. Search for timers, retries, streaming, polling, mutable globals, shared fixtures, and async cleanup.
3. Prefer deterministic clocks, explicit awaits, and isolated fixtures.
4. Confirm the fix removes nondeterminism rather than increasing timeouts.

Minimum proof:

- Before/after flake evidence, or a deterministic contract test that captures the race-prone invariant.
