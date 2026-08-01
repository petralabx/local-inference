---
name: automate
description: Create Cursor Automations. Use only when the user explicitly asks for Cursor Automations, scheduled Cursor agents, or opening the Automations editor with a reviewed draft.
environments:
  - local
---
# Create Cursor Automation

Use this skill only for **Cursor Automations**. Do not assume generic phrases like "automate this" mean Cursor Automations; clarify unless the user explicitly names Cursor Automations, scheduled Cursor agents, or the Automations editor.

## Finish Availability

Before drafting, confirm this session can finish the handoff. If neither the Automations editor opener nor an equivalent resource opener is available, stop and say: "Please use this skill in the Agents Window."

Do not inspect backend automation create/update/list tools to bypass the editor. The finish path is: reviewed draft -> user approval -> user says they are ready -> open Automations editor.

## Execution Spine

1. Confirm this is a Cursor Automation request.
2. Capture trigger, action, outcome, and target integrations.
3. Discover picker-backed integration values when possible: GitHub repo, Slack channel, PagerDuty service, Linear/Sentry team/project.
4. Resolve or explicitly defer required portal fields.
5. Present a compact Markdown draft table, not YAML.
6. Ask for approval.
7. After approval, ask whether the user is ready to open the editor.
8. Open the Automations editor with the reviewed draft.

## House Rules

- Plain language only in user-facing chat. Do not expose MCP/tool/proto names unless the user asks.
- No YAML in finalization. Validate internal payloads privately.
- Creation-only. Do not list, inspect, update, or search existing Cursor Automations from chat.
- No automatic fallbacks. Do not submit, open random URLs, or paste browser prefill links.
- Integration discovery is allowed only for connected picker-backed values.
- Repo file references are allowed only when the automation runs in the same repo and the referenced file is committed on the branch the automation will check out.

## Required Completeness Checks

Before showing the draft table, resolve or defer these fields:

- Slack trigger channels: choose specific channels or explicitly defer to the editor.
- Slack action destination: triggering thread, channel, or DM; never infer from a Slack trigger alone.
- Git trigger scope: repo/org/branch for PR, push, or CI triggers.
- Tools/actions: include only tools that are available and appropriate.
- Deferred values: list all intentional gaps in the draft table's "To finish in editor" row.

## MCP / Integration Rules

Only use dashboard-backed, editor-visible MCP integrations for automation actions. Local-only project MCPs, Cursor IDE browser tools, app-control tools, and extension-local servers are not valid automation MCP actions.

When selecting an MCP server:

- Read the live catalog exposed to the session.
- Use the configured server name, not internal folder identifiers.
- If the server is missing, disabled, or local-only, leave it out and record the setup need.
- If auth is required, stop drafting and offer to start auth when inline auth is available.
- Never defer OAuth to the Automations editor for a prefilled MCP row; it can discard unsaved draft state.

## Draft Table Shape

Show a compact table with these rows:

| Field | Draft |
|---|---|
| Name | Short, specific automation name |
| Description | One sentence |
| Trigger | Schedule, Slack, GitHub, CI, manual, or other |
| Tools | Plain-language list |
| Instructions | What the agent should do |
| Resolved settings | Repo, branch, channel, service, etc. |
| To finish in editor | Any intentionally deferred fields |

After the table, ask: "Approve this draft?" Do not open the editor until approved and the user says they are ready.

## Trigger Guidance

- Scheduled: capture cadence, timezone intent, and day/time. Use human-facing ET labels when presenting schedules.
- GitHub PR: capture repo/org, event, branch filters, and expected action.
- Slack: capture trigger channel(s), whether replies go to thread or channel, and any read/write scope.
- Manual: capture what the user will provide each run and the expected output.

## Instruction Quality

Good automation instructions include:

- Goal and success criteria.
- Inputs the agent should inspect.
- Constraints and non-goals.
- Tools/integrations it may use.
- Output format.
- Verification or escalation behavior.

Avoid vague instructions like "handle this" or "do the usual" unless the referenced workflow is explicitly described in the draft.

## Safety Stops

Stop and ask before editor handoff when:

- The target integration is unavailable or unauthenticated.
- Required trigger scope is unclear.
- The automation would act destructively or externally without approval.
- The user asks to edit an existing automation instead of creating one.
- The finish path is unavailable in this session.
