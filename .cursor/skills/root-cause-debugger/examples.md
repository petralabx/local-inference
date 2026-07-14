# Examples

These examples show how the skill should behave. They are not scripts; they are expected debugging patterns.

## Example 1: Chat Feels Like Typing Into The Abyss

User prompt:

```text
chat messages to the swarm never return successful completions, it's like i'm typing into the abyss, I don't know what the root cause is and why our chat is so unreliable, please fix it! /root-cause-debugger
```

Expected agent behavior:

1. Classify as `chat`, `swarm-dispatch`, `api`, possibly `e2e/browser`.
2. Read `domain-playbooks.md` Chat Reliability and Swarm Dispatch sections.
3. Reproduce with the narrowest available chat contract or browser flow.
4. Trace: UI input -> `chat/stream` route -> `chat-dispatch` -> queue -> callback -> persisted completion -> UI render.
5. Keep hypotheses such as:
   - Dispatch is never created.
   - Dispatch callback cannot map back to chat thread.
   - UI stream listens to the wrong event or never reconciles completion.
6. Confirm one broken transition with test/browser/API evidence.
7. If no contract exists, use `reliable-tdd-loop` to add one failing invariant first.
8. Fix the smallest layer.
9. Verify with targeted chat/dispatch contract, `npm run test:contracts --prefix apps/vmc-web`, typecheck if touched, and browser evidence if UI-visible.

Expected final report:

```text
Symptom: Chat accepted messages but completions never appeared in the thread.
Root cause: <specific broken transition>
Evidence: <failing test/browser/network/log evidence>
Fix: <minimal change>
Verification: <commands and browser/API checks>
Residual risk: <remaining coverage/runtime risk>
Follow-up: <optional>
```

## Example 2: Todo Stuck In Running

User prompt:

```text
todos keep getting stuck as running and never complete after the swarm finishes /root-cause-debugger
```

Expected agent behavior:

1. Classify as `todos`, `swarm-dispatch`, `flaky/race` if intermittent.
2. Run or inspect `todo-dispatch-contracts` and relevant route/store tests.
3. Trace: todo store -> dispatch link -> queue callback -> status reconciliation -> stream/UI.
4. Check lease fields, callback mapping, stale status overwrite, and stream state.
5. Add a regression contract if callback mapping or reconciliation lacks coverage.
6. Verify with todo dispatch contract, route contracts, typecheck, and UI/API evidence if the flow is visible.

## Example 3: Trading Promotion Gate Is Wrong

User prompt:

```text
trading v2 says a strategy is ready to promote even though paper performance is below threshold /root-cause-debugger
```

Expected agent behavior:

1. Classify as `trading`, `api`, `db`, possibly `external-integration`.
2. Enforce paper/staging-only.
3. Reproduce with the narrow trading contract or `npm run trading-v2:readiness --prefix apps/vmc-web`.
4. Trace: trading API -> trading-v2 store -> KPI/readiness snapshot -> promotion gate threshold.
5. Check stale snapshots, threshold constants, baseline/current trial mixup, and riskguard status.
6. Verify with trading readiness plus targeted promotion/riskguard tests.

Never trigger live trades or broker actions from this workflow.

## Example 4: CI Fails But Local Looks Green

User prompt:

```text
CI is red on the VMC route contracts but I can't reproduce it locally /root-cause-debugger
```

Expected agent behavior:

1. Classify as `ci-only` and likely `contract`.
2. Identify exact CI command and failure output.
3. Run the same command locally if dependencies are available.
4. Compare Node/npm versions, dependency install, path assumptions, environment variables, order-dependent tests, and time-sensitive tests.
5. Avoid weakening tests unless they are proven invalid.
6. Verify with the CI-equivalent command and wider gate.

## Example 5: Browser Button Does Nothing

User prompt:

```text
the dispatch button does nothing in the browser /root-cause-debugger
```

Expected agent behavior:

1. Classify as `e2e/browser`, `api`, possibly `swarm-dispatch`.
2. Use browser tools: list tabs, snapshot, click by ref, snapshot again.
3. Inspect console and network evidence.
4. If request never fires, trace component state/event handler.
5. If request fails, trace the route and response shape.
6. If request succeeds but UI does not update, trace stream/poll/cache/render state.
7. Verify with browser evidence and targeted E2E or contract tests.

## Example 6: MCP Tool Exists But Fails

User prompt:

```text
VMC MCP says the todo tool exists but calling it fails /root-cause-debugger
```

Expected agent behavior:

1. Classify as `external-integration`, `mcp`, `api`.
2. Read the MCP descriptor JSON before any `CallMcpTool`.
3. Probe runtime availability with a safe read-only tool when possible.
4. Distinguish descriptor/runtime mismatch from auth failure and API failure.
5. Report governance blocker if MCP runtime is out of sync, and continue non-blocked local verification.

## Example 7: Flaky Race In Stream Updates

User prompt:

```text
sometimes the chat completion appears, sometimes it doesn't /root-cause-debugger
```

Expected agent behavior:

1. Classify as `flaky/race`, `chat`, `e2e/browser`.
2. Record baseline flake evidence before changing timeouts.
3. Inspect stream subscription lifecycle, async cleanup, stale closures, optimistic state, and polling intervals.
4. Prefer deterministic contract coverage over increasing delays.
5. Verify by proving the stream/reconciliation invariant and rerunning the narrow check multiple times if appropriate.
