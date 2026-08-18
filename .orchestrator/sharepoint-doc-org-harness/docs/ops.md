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

Until proven, install once daily at 06:00 America/Toronto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-organizer-cadence.ps1 -Mode daily -Install
```

After proof:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-organizer-cadence.ps1 -Mode every-4h -Install
```

The job runs `scripts/run-organizer-digest.ps1`. That script loads `LOCAL_LITELLM_MASTER_KEY` from `C:\Users\vince\local-inference\.env.local` and never prints the key. Interactive logon only (Vince signed in on VTA). On failure the inbox stays for the next run — no paid-host fallback.

Mail remainder (attachments older than 90 days, Outlook folders unchanged):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/mail-outlook-pass.ps1 -Mode remainder
```

Unique Petra archive and leftover VincePersonal roots:

```powershell
python -m harness.cli.main drain --report data/reports/drain-archive.json --only 09_Archive --only _root
python -m harness.cli.main drain --report data/reports/fold-roots.json --source-root "<VincePersonal>" --map config/legacy_roots.yaml
```

Hide drained Petra sources only after unique files are gone. Never hides Vince Personal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/hide-petra-sources.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/hide-petra-sources.ps1 -Apply
```

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
