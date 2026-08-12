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

Steady-state classify/digest uses Dell LiteLLM only (`http://100.103.33.54:4000/v1`).  
Config rejects paid hosts (`api.openai.com`, `api.anthropic.com`, `api.x.ai`).

## Inbox ceiling

Active files under `00_Inbox` (excluding `_` helper folders) should stay ≤100.  
Digest report sets `ceiling_breach` when over.
