---
name: sdk
description: Guide users building apps, scripts, CI pipelines, or automations on top of the Cursor SDK - TypeScript (`@cursor/sdk`) or Python (`cursor-sdk` / `cursor_sdk`). Use when the user mentions integrating, installing, or writing code against the Cursor SDK; says `Agent.create`, `Agent.prompt`, `Agent.resume`, `agent.send`, `run.stream`, `run.messages`, `CursorAgentError`, `@cursor/sdk`, `cursor-sdk`, or `cursor_sdk`; asks to run Cursor agents programmatically from a script, CI/CD pipeline, GitHub Action, backend service, or other code outside the Cursor IDE; wants to pick between local and cloud runtime, configure MCP servers for an SDK agent, or handle streaming, cancellation, or errors.
---
# Cursor SDK

The Cursor SDK runs Cursor agents programmatically. It has two variants:

- TypeScript: `@cursor/sdk` from npm.
- Python: `cursor-sdk` / `cursor_sdk` from pip.

Use this skill to help users build working integrations quickly and avoid common SDK traps.

## Pick The Language

Choose before writing code:

1. If the user names TypeScript or Python, use that.
2. If the repo clearly signals one stack, follow it: `package.json`/`.ts` -> TypeScript, `pyproject.toml`/`.py` -> Python.
3. If unclear, ask: "TypeScript or Python?"

## Voice And Posture

When the user explicitly names the SDK, skip sales language and go straight to design/code. Do not open with praise like "good news" or restate their goal. If they describe a problem the SDK might fit but do not name it, ask whether they want a Cursor SDK design before committing to that path.

## Invocation Patterns

### 1. One-shot prompt

Use `Agent.prompt(...)` for fire-and-forget scripts, CI steps, and simple jobs with no follow-up.

TypeScript sketch:

```typescript
import { Agent } from "@cursor/sdk";

const result = await Agent.prompt("Review this diff", {
  apiKey: process.env.CURSOR_API_KEY!,
  local: { cwd: process.cwd() },
});
console.log(result.status, result.result);
```

Python sketch:

```python
import os
from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

result = Agent.prompt(
    "Review this diff",
    AgentOptions(
        api_key=os.environ["CURSOR_API_KEY"],
        local=LocalAgentOptions(cwd=os.getcwd()),
    ),
)
print(result.status, result.result)
```

### 2. Durable agent with follow-ups

Use `Agent.create(...)` plus `agent.send(...)` when you need streaming, multiple turns, cancellation, or status listeners.

TypeScript pattern:

```typescript
import { Agent } from "@cursor/sdk";

await using agent = await Agent.create({
  apiKey: process.env.CURSOR_API_KEY!,
  local: { cwd: process.cwd() },
});

const run = await agent.send("Find the bug in src/auth.ts");
for await (const event of run.stream()) {
  // handle assistant text, tool events, status, etc.
}
await run.wait();
```

Python pattern:

```python
from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

with Agent.create(AgentOptions(local=LocalAgentOptions(cwd="."))) as agent:
    run = agent.send("Find the bug in src/auth.py")
    for event in run.stream():
        pass
    run.wait()
```

### 3. Resume existing agent

Use `Agent.resume(...)` when the integration stores an agent id and returns later for another prompt, status check, or cancellation. Persist ids in your own database or job store.

## Local Vs Cloud Runtime

- Local runtime runs on the caller machine against a local `cwd`. Use for developer scripts, repo-local bots, and CI with the checkout already present.
- Cloud runtime runs on Cursor infrastructure against a cloned repo. Use when callers should not host the run environment or need remote execution.

Ask before choosing cloud if the repo, credentials, or data residency matter.

## Auth

- Read `CURSOR_API_KEY` from the environment or secret manager.
- Never hardcode keys in examples or committed code.
- In CI, wire secrets through the CI secret store.
- Catch SDK-specific errors separately from agent-run failures when the language exposes typed errors.

## Streaming And Lifecycle

- Streaming is optional; use it only when the caller needs progressive output.
- Always wait for final completion before treating the run as done.
- Dispose/close long-lived agents (`await using` in TypeScript, context managers in Python) to avoid resource leaks.
- Distinguish transport/API errors from a completed run whose agent result says it failed.

## MCP Configuration

When configuring MCP servers for SDK agents:

- Use the SDK's supported MCP configuration shape for the chosen runtime.
- Do not pass local Cursor IDE-only MCP servers unless the SDK runtime can actually access them.
- Keep secrets out of committed MCP config.
- Validate server availability with a small test run before building a workflow around it.

## Production Practices

- Add timeouts and cancellation paths.
- Persist agent/run ids for long jobs.
- Log status transitions and final result metadata.
- Capture stderr/exception detail for operator debugging without leaking secrets.
- Keep prompts explicit about repo path, branch, task, output format, and verification.
- Make model selection configurable instead of hardcoding a single model in reusable packages.

## Common Traps

- Picking local when the job needs a clean hosted environment, or cloud when local files/secrets are required.
- Treating SDK call success as task success; inspect the run status/result.
- Forgetting to wait for the final run result after streaming.
- Leaking keys through examples, logs, or exceptions.
- Trying to resume a run without persisting the agent/run identifiers.
- Assuming every runtime supports every operation.

## What This Skill Does Not Cover

- General Cursor IDE usage.
- Cursor Automations authoring; use `automate` for that.
- Browser UI testing.
- Product support for undocumented SDK internals.
