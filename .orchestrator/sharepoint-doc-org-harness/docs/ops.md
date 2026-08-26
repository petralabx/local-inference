# Operator surface — SharePoint doc org harness

## Roles

| Machine | Role |
|---------|------|
| Dell-VTA | **Single writer** — scheduled `harness digest` |
| Laptop (`taylorvalton`) | Query / reverse only (`harness where`, `harness reverse`) |

Writer lock: VTA creates `data/writer.lock` while digest runs. Laptop must not run mutating commands against the same journal.

## Naming and ledger

Digest applies `YYYY-MM-DD_PREFIX_Readable Title_vNN.ext` (ADR 0011 / 0024).
Vince does not type that law. Prefix, type, date, and version live in the
Document ledger table in `data/journal.sqlite3`. `harness where` reads the
ledger first. Vince Node projection is fail-open (`VMC_API_KEY` +
`VMC_BASE_URL`). Filing continues if Brain is down.

Digest skips already-hashed files unless a correction rule matches and the
file is not already in that rule's `target_folder`. Relabel keeps the current
folder for LLM/heuristic names; a correction-rule match still rehomes.
Already-filed homes with no rule hit stay on the hash/ledger skip. Relabel
the rest:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-organizer-relabel.ps1 -Limit 20
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-organizer-relabel.ps1
```

VTA is the only writer. The laptop mount is the same VincePersonal site — verify sync; do not run a second relabel there. Capture folders (`_from_*`) are skipped so a live mail pass is not stolen.

## Harvest stamp (Title + Party/Prefix/Home)

After digest and relabel name a file, the Organizer stamps SharePoint ranking
surfaces. Metadata-only backfill (no rename) of already-filed `00`–`06` homes:

```bash
python -m harness.cli.main stamp --report data/reports/stamp.json --limit 20
python -m harness.cli.main stamp --report data/reports/stamp.json
```

Skips `_from_*` capture, secrets, and code trees. Walks `00`–`06` homes one
folder at a time (the library is over the 5k view threshold; do not
`$filter=FileLeafRef`). Leftover root trees are not folded. Graph listItem
fields when a delegated token exists; Office/PDF Title/Subject/Keywords on
the sync-root even when Graph is offline (journal `columns_skipped`).

### Delegated Graph login (VTA, ADR 0026)

First interactive login as `vince@petrasoap.com` (device-code; no pasted
token, no app-only secret, no cookie scrape):

```powershell
python -m harness.cli.main graph-login
```

Silent cache: `data/msal_graph_cache.bin` (gitignored). Digest / relabel /
stamp pick up `LiveGraphDriveClient` when that cache (or an Azure CLI
session for the same UPN) exists. Scheduled jobs stay silent. Cloud Agent
VMs stay offline unless that cache is present.

Locked site-column contract: display names Party / Prefix / Home; internal
names `OrganizerParty` / `OrganizerPrefix` / `OrganizerHome`; site columns on
Vince Personal, added to the default Document content type, all three indexed.
Stamp list-item **Title** to the peeled readable title. Do not rename the
native Title field. Do not create Term store, Syntex, or custom ranking.
Do not enable Autofill on those three columns
([autofill-setup](https://learn.microsoft.com/en-us/microsoft-365/documentprocessing/autofill-setup)).

### Copilot / search (Vince Personal must stay in the index)

Microsoft Copilot uses library column metadata + Title when a library or folder
is attached. Folder names are not Copilot classification. Party/Prefix/Home
are that signal.
[Semantic indexing for Microsoft Copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot)
(updated 2026-08-18).

Vince Personal **Allow this site to appear in search results** must stay
**Yes** (Site settings → Search and offline availability). **No** drops the
site from both Microsoft Search and the semantic index
([make-site-content-searchable](https://learn.microsoft.com/en-us/sharepoint/make-site-content-searchable);
same exclusion steps on the Copilot page).

Do not archive `00`–`06` homes as cleanup. Archived SharePoint data is not in
the semantic index
([supported content types](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot#supported-content-types);
[Archive FAQ](https://learn.microsoft.com/en-us/microsoft-365/archive/archive-faq)
—“Does archived content get returned in Microsoft Copilot queries? No”).

### One-time tenant-admin search schema (Python cannot finish this)

Crawled properties `ows_OrganizerParty`, `ows_OrganizerPrefix`, and
`ows_OrganizerHome` exist only after the site columns are created and the
library is crawled. Mapping them to refinable managed properties requires a
Search Administrator. Follow Microsoft’s search-schema docs; do not invent a
click path.

1. Open tenant Search Schema from SharePoint admin center → More features →
   Search → Manage Search Schema, as documented in
   [Manage the search schema in SharePoint](https://learn.microsoft.com/en-us/sharepoint/manage-search-schema)
   (“Create a managed property by renaming an existing one” and
   “Map a crawled property to a managed property”).
2. Unused refinable strings (alias + crawled mapping) from that same page’s
   [Default unused managed properties](https://learn.microsoft.com/en-us/sharepoint/manage-search-schema#default-unused-managed-properties)
   table: `RefinableString00`–`RefinableString219` are Query/Retrieve/Refine/Sort.
3. Map and alias (once each unused RefinableString is still unmapped):

   | Crawled property | Managed property | Alias |
   | --- | --- | --- |
   | `ows_OrganizerParty` | `RefinableString00` | Party |
   | `ows_OrganizerPrefix` | `RefinableString01` | Prefix |
   | `ows_OrganizerHome` | `RefinableString02` | Home |

   Microsoft: for built-in managed properties you change crawled mappings and
   the **alias** setting; custom managed properties cannot be refinable in
   Microsoft 365 — reuse RefinableStringNN.
   Overview of crawled vs managed properties:
   [search-schema-overview](https://learn.microsoft.com/en-us/sharepoint/search/search-schema-overview).
4. After mapping, request a re-index of the library as that page describes.
   Until this admin step, Graph Title + site columns still rank All-tab Title
   and Copilot library-scoped metadata; they are not refiners.

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
