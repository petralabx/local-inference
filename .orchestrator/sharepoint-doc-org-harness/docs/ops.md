# Operator surface — SharePoint doc org harness

## Roles

| Machine | Role |
|---------|------|
| Dell-VTA | **Single writer** — scheduled `harness digest` |
| Laptop (`taylorvalton`) | Query / reverse only (`harness where`, `harness reverse`) |

Writer lock: VTA creates `data/writer.lock` while digest runs. Laptop must not run mutating commands against the same journal.

## Daily digest

```bash
cd .orchestrator/sharepoint-doc-org-harness
set HARNESS_CONFIG=config/local.yaml
python -m harness.cli.main digest --report data/reports/digest-latest.json
```

Dry run (no moves):

```bash
python -m harness.cli.main digest --dry-run --report data/reports/digest-dry.json
```

## Windows Task Scheduler (VTA)

1. Action: start a program  
   `C:\Path\To\python.exe`  
   Arguments: `-m harness.cli.main digest --report D:\harness\data\reports\digest-latest.json`  
   Start in: harness package root
2. Trigger: daily off-hours (e.g. 02:00)
3. Run whether user is logged on; highest privileges only if needed for sync root ACLs
4. On failure: leave inbox untouched for next run (fail closed — no cloud LLM fallback)

## Inference policy

Steady-state classify/digest uses Dell LiteLLM
(`http://100.103.33.54:4000/v1`) with Spark aliases `local-driver` /
`local-coder`. Export `LOCAL_LITELLM_MASTER_KEY` before digest. Clients
must send `Authorization: Bearer <key>`. A bare `GET /v1/models` returns
HTTP 500 (no virtual-key DB), not a clean 401. Config rejects paid hosts
(`api.openai.com`, `api.anthropic.com`, `api.x.ai`).

## Inbox ceiling

v1 has no inbox ceiling (ADR 0019). `inbox_active_ceiling: 0` disables
`ceiling_breach`.

## Cadence

Until proven: once daily. After proof: 06:00 / 10:00 / 14:00 / 18:00
America/Toronto via `scripts/install-organizer-cadence.ps1`.

## Known-folder redirect

`scripts/redirect-known-folders.ps1` defaults to dry-run. Apply on VTA
only while Vince is present. taylorvalton waits until he is at that machine.

Live execute steps: `docs/execute-checklist.md`.
