---
name: vmc-sync
description: Keep Cursor sessions synchronized with VMC (Mission Control) todo/project state via the vmc-context MCP server — checkout, progress, and complete with evidence. Use when working on a VMC-tracked todo, claiming a "Send to Cursor" handoff, or when the user references Mission Control tasks, the roadmap, or a todo ID. Requires the vmc-context MCP server or VMC API access.
---

# VMC Sync Skill

Use when working on tasks tracked in VMC (Mission Control). This skill keeps Cursor sessions synchronized with VMC's todo/project state so the swarm and human always see accurate progress.

## MCP Tools Available

These tools connect to VMC via the `vmc-context` MCP server.
Set `VMC_BASE_URL` in `~/.cursor/mcp.json` for each box:
- Local VMC runtime: `http://localhost:3100`
- Shared hosted VMC: `https://missioncontrol.tayloralton.com`

| Tool | When to Use |
|------|-------------|
| `vmc_get_context` | Session start, before major decisions, when switching tasks |
| `vmc_self_check` | First step on a new machine/session to verify base URL + API key + auth |
| `vmc_claim_handoff` | Claim a VMC “Send to Cursor” handoff from a specific run ID |
| `vmc_checkout_task` | Before starting work on any tracked todo |
| `vmc_report_progress` | After completing a subtask or logical milestone (~every 10-15 min) |
| `vmc_complete_task` | When work is done, with evidence (commit SHA, files changed) |
| `vmc_get_roadmap` | To decide what to work on next |

## Session Lifecycle

### 1. On Session Start
Call `vmc_self_check` first to validate:
- `VMC_BASE_URL` target
- `VMC_API_KEY` presence in MCP process
- Auth to `/api/vmc/cursor/context`

Then call `vmc_get_context` with `depth=compact` to load:
- Active projects and their progress
- High-priority todos sorted by urgency
- Blocked items needing attention
- System health score

Use this context to orient before doing any work.

If VMC opened this session from a “Send to Cursor” handoff, call
`vmc_claim_handoff` with the provided `runId` first. The claim binds this Cursor
worker session to the exact handoff and returns the generated task prompt plus
the normal checkout/progress/complete instructions.

### 2. Before Starting a Task
Call `vmc_checkout_task` with the todo ID to:
- Claim it (prevents the swarm from double-dispatching)
- Set status to "progress" with agent = "Cursor"
- Get back the full todo with project context

If checkout returns **409 Conflict**, the task is already assigned. Re-fetch context to see who has it.

### 3. During Work — Report Progress
Call `vmc_report_progress` after completing logical chunks:
- After finishing a significant subtask
- After ~10-15 minutes of work on the same task
- When changing approach or discovering blockers

Include a brief `notes` field describing what was done.

### 4. On Task Completion
Call `vmc_complete_task` with:
- `evidence`: must include the exact verification command(s) run and confirmation of exit 0 (see `.cursor/rules/agent-testing-contract.mdc` for the verification matrix)
- `commitSha`: the git commit hash (if applicable)
- `prUrl`: pull request URL (if applicable)
- `filesChanged`: list of files modified
- `codeChanged: true` and `verificationCommands` for code-changing work
- `promotionStage`: use `agent_done` for local completion, then let GitHub/VMC promotion evidence advance through `qa-review`, `merged`, `deployed`, and `completed`

The task will move to QA review automatically, but that is not the same as merged or deployed.

### 5. Choosing Next Work
Call `vmc_get_roadmap` to see what's highest priority across all projects.

## Staleness Mitigation

- **Re-fetch context** when switching to a different task
- **Re-fetch after 15+ minutes** of work on the same task
- **Use `depth=full`** before making architectural decisions (adds descriptions, blockers, decisions)
- **On 409 from checkout**, re-fetch context to see current assignments
- **When VMC is unreachable**, continue working but note the desync — do not block

## Fallback (No MCP)

If the MCP server is not configured, use Shell tool to call the API directly:

```bash
source ~/load-secrets.sh
# Set this once per box/environment
VMC_BASE_URL="${VMC_BASE_URL:-https://missioncontrol.tayloralton.com}"

# Get context
curl -s "$VMC_BASE_URL/api/vmc/cursor/context?depth=compact" \
  -H "X-API-Key: $VMC_API_KEY" | jq .

# Checkout task
curl -s -X POST "$VMC_BASE_URL/api/vmc/cursor/checkout" \
  -H "X-API-Key: $VMC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"todoId": "todo-xxx"}'

# Report progress
curl -s -X POST "$VMC_BASE_URL/api/vmc/cursor/progress" \
  -H "X-API-Key: $VMC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"todoId": "todo-xxx", "progressPct": 50, "notes": "Completed X"}'

# Complete task
curl -s -X POST "$VMC_BASE_URL/api/vmc/cursor/complete" \
  -H "X-API-Key: $VMC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"todoId": "todo-xxx", "evidence": "Implemented X. Verification: npm run test --prefix apps/vmc-web && npm run typecheck --prefix apps/vmc-web (exit 0)."}'
```
