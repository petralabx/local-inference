---
name: session-brain
description: Manually compose and submit a company-brain SessionArtifact when the runtime has no session-end hook support (or the hook failed open). Use at the end of any session that changed code, made a decision, or learned something — not for trivial Q&A. Requires VMC_API_KEY; falls back to a local offline-queue file when VMC is unreachable.
---

# Session Brain Skill

Every agent session that changes code, makes a decision, or learns something
**must** leave a structured `SessionArtifact` behind so it becomes part of the
company brain (searchable via VMC's Knowledge Observatory and memory-graph
rollups). Trivial Q&A sessions with no code change, decision, or lesson may
skip this.

Cursor (`stop`/`sessionEnd` hooks) captures this automatically via
`scripts/cursor-hooks/session_artifact_lib.py`. This skill is for everything
else: Claude Code (its `Stop`/`SessionEnd` hook wiring is pending — see the
company-brain P3 deferral), runtimes without hook support, or a manual
submission when you know the hook didn't fire (e.g. this session ran in a
detached worktree).

## Schema (SessionArtifact v1)

Canonical contract: `apps/vmc-web/src/lib/vmc/knowledge/session-artifact.ts`
(`SessionArtifactV1Schema`). Department taxonomy: `config/departments.yaml`.

| Field | Required | Notes |
|---|---|---|
| `schema_version` | yes | Always `1` |
| `runtime` | yes | `cursor` \| `claude-code` \| `hermes` \| `swarm` \| `other` |
| `session_id` | yes | Stable id for this session (conversation id, or a UUID) |
| `started_at` / `ended_at` | yes | ISO 8601 timestamps |
| `repo` | yes | Repo name, e.g. `agentic-swarm` |
| `branch` | yes | Current git branch |
| `project_slug` | no | e.g. `company-brain`, if the work maps to a tracked project |
| `department` | no | One of `config/departments.yaml` ids (`dev`, `research`, `qa`, `ops`, `trading`, `manufacturing`) |
| `title` | yes | One-line summary of the session |
| `summary` | yes | What happened, in prose (markdown ok) |
| `decisions[]` | no | Notable decisions made, one per entry |
| `lessons[]` | no | Notable lessons learned, one per entry |
| `files_touched[]` | no | Repo-relative paths changed |
| `evidence[]` | no | `{kind, ref}` pairs, e.g. `{"kind": "pr", "ref": "https://github.com/.../pull/123"}` |
| `tags[]` | no | Extra free-form tags (repo/project/department tags are added automatically) |

## Submit via curl

```bash
VMC_BASE_URL="${VMC_BASE_URL:-http://localhost:3100}"  # or https://missioncontrol.tayloralton.com

curl -s -X POST "$VMC_BASE_URL/api/vmc/knowledge/session-artifact" \
  -H "X-API-Key: $VMC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": 1,
    "runtime": "other",
    "session_id": "manual-2026-07-01-abc123",
    "started_at": "2026-07-01T20:00:00.000Z",
    "ended_at": "2026-07-01T21:15:00.000Z",
    "repo": "agentic-swarm",
    "branch": "proj/company-brain/phase-3-hooks",
    "project_slug": "company-brain",
    "department": "dev",
    "title": "Implemented session-end capture hooks",
    "summary": "Added Cursor stop/sessionEnd hooks and a session-brain skill for manual submission.",
    "decisions": ["Route the Cursor and Claude Code hooks through one shared lib module"],
    "lessons": ["Hook payloads carry event metadata, not a full transcript — summaries are best-effort"],
    "files_touched": ["scripts/cursor-hooks/session_artifact_lib.py"],
    "evidence": [{"kind": "commit", "ref": "abc1234"}],
    "tags": []
  }'
```

A 2xx response confirms ingestion (`memory.items`, `memory_type: session_artifact`).

## Offline-queue fallback

If `VMC_API_KEY` is missing, VMC is unreachable, or the curl call fails, do not
block on it — write the same JSON body to a local file instead so it is not
lost:

```bash
mkdir -p "artifacts/session-brain/$(date -u +%F)"
# write the JSON body above to:
#   artifacts/session-brain/<yyyy-mm-dd>/<session_id>.json
```

This mirrors the offline queue used by the automated hooks
(`scripts/cursor-hooks/session_artifact_lib.py::write_offline_queue`). Queued
files are not auto-replayed yet — flag them to an operator or replay manually
with the curl command above once VMC is reachable.

## Rule of Thumb

- **Leave an artifact:** code changed, a decision was made, a lesson was
  learned, or non-trivial research/investigation happened.
- **Skip it:** pure Q&A with no code change, no decision, and nothing worth
  remembering later.
