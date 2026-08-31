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
Already-filed homes with no rule hit stay on the hash/ledger skip unless the
filename fails `is_organizer_name` (stacked dates, leftover folder prefixes
such as `01_CLIENTS_PROJECTS` / `BUSINESS_OPS` / `PERSONAL`, or visual
`vNN_vNN`) or the peeled title is missing an entity or a topic. A single
generic word (`Untitled`, `Document`, `Scan`, `File`, `Image`) or a topic-only
title (`Invoice`, `Contract`) is a miss and is re-picked. The title slot is
always `Entity Topic` (Happy Yards Invoice, K18 Stability Quote); PREFIX stays
the taxonomy code. If the entity cannot be named, hold in
`00_Inbox/_Unsorted_Imports` — do not invent a party. OrganizerParty equals
that entity. Stacked law failures with a good Entity Topic title are still
peeled first — `peel_organizer_title` plus `normalize_organizer_prefix` — with
no model call. Correction rules stay first-class for prefix, optional party,
and rehome. Relabel does not walk leftover VincePersonal roots (`artifacts`,
`Projects`, …) and still skips secrets and code trees.

`--limit` applies after that priority, so a proof walk spends its budget on
stacked leftovers, then weak titles, not on already-law Entity Topic files.

Proof (VTA only), then full:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-organizer-relabel.ps1 -Limit 20
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-organizer-relabel.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-organizer-relabel.ps1 -Only 02_Business_Ops,03_Marketing_Creative,04_Admin,06_Reference
```

VTA is the only writer. The laptop mount is the same VincePersonal site — verify sync; do not run a second relabel there. Capture folders (`_from_*`) are skipped so a live mail pass is not stolen. Do not run this walk to fold leftover trees.

`--only` (CLI and `run-organizer-relabel.ps1 -Only`) constrains the home list
so an unstall of 02/03/04/06 does not re-walk 05/01/00. Relabel writes
`homes` and `completed_homes` into the JSON report. `harness unstall --report`
treats `finished_at` plus a completed home list as DONE even when the writer
pid is dead. Pid-dead plus an unfinished report restarts remaining homes
only. Held files stay unsorted; the report `held_reasons` histogram
(`unknown_entity`, `weak_title`, `already_entity_topic_llm_empty`,
`skip_secret`, `skip_telegram`, `skip_bad_date`) is for later Vince
correction rules — do not invent rules from it. A filename that already
parses as Entity Topic keeps that entity; do not LLM-hold it. Secrets
including `.git-credentials` and `.gitconfig` skip before classify.

Harvest (including `--dry-run`) refuses a home that has a live relabel lock
under `data/home_locks/`. Do not start a harvest dry-run of 02/03/04/06
against a live Entity-Topic relabel of those same homes.

Graph Title/Party/Prefix/Home 404s after a local OneDrive rename are skips,
never stamp success. After the rename pass:

```bash
python -m harness.cli.main stamp --report data/reports/stamp-backfill.json --backfill
```

retries by current path or Graph item id. Leftover-tree fold stays dry-run
until that backfill exists.

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
stamp / sync-audit / harvest pick up `LiveGraphDriveClient` when that cache (or
an Azure CLI session for the same UPN) exists. Scheduled jobs stay silent.
`stamp` walks Graph folders as well as local files that resolve, and logs the
Graph skip/404 reason instead of a silent `columns_skipped`. Cloud Agent VMs
stay offline unless that cache is present.

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

## Sync audit (local vs SharePoint)

OneDrive Explorer can show files the library no longer has (2026-08-23
rule-rehome: OSError 22, then folder-name compare missed local-only files).
SharePoint `ItemCount` is not a recursive file count, and Vince Personal is
over the 5k list-view threshold, so this job walks **one folder at a time**.
Graph drive `children` or SharePoint REST
`GetFolderByServerRelativeUrl` Files/Folders — never a library-wide unindexed
`$filter`, and never the search API (not a completeness check).

Report-only. Same digest skip rules (code trees, secrets, exclude globs). Does
not upload, rename, or stamp.

Dry-run (path inventory, no content hashes) — default report
`data/reports/sync-audit.json`:

```bash
python -m harness.cli.main sync-audit --dry-run
python -m harness.cli.main sync-audit --dry-run --only 05_Personal --report data/reports/sync-audit-personal.json
```

Hash compare when Graph provides `sha256Hash` (ignored with `--dry-run`):

```bash
python -m harness.cli.main sync-audit --hashes --report data/reports/sync-audit.json
```

Live listing on VTA uses the same delegated MSAL cache as `stamp` (`harness
graph-login`). Do not paste a Graph token.

```powershell
python -m harness.cli.main graph-login
python -m harness.cli.main sync-audit --dry-run --backend graph
python -m harness.cli.main sync-audit --dry-run --only 05_Personal --report data/reports/sync-audit-personal.json
```

`--cassette` stays for fixture tests. REST backend still accepts
`HARNESS_SP_TOKEN` when MSAL is not used; Graph default does not require an
env token.

Cloud Agent VMs cannot see `C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd\Vince Personal - Documents`. Do not treat a cloud cassette run as the live audit.

The JSON report lists `local_only` (on disk, no server item), `server_only`,
`path_mismatches` (same name, different relative path — the rehome/sync-drop
case), and optional `hash_mismatches`.

## Harvest (Graph upload missing files, then stamp)

OneDrive Explorer moves are forbidden for this job (2026-08-23 OSError 22
deleted cloud originals). Graph upload is additive and is the only allowed
missing-file path. Files under 4MB use `PUT /content`; larger files use
`createUploadSession` plus chunked PUT. Missing parent folders are created.
Secrets and code trees are skipped. A server item with a different size fails
unless `--replace` is explicit; identical size is skipped.

```powershell
python -m harness.cli.main harvest --report data/reports/harvest.json --dry-run --only 05_Personal
python -m harness.cli.main harvest --report data/reports/harvest.json --apply --only 05_Personal
python -m harness.cli.main harvest --report data/reports/harvest.json --apply --audit-report data/reports/sync-audit.json
```

`--apply` from VTA (or any host) is allowed when the job only talks to Graph.
It is refused on non-Windows only if it would move local OneDrive files.
Default stays dry-run. Fold leftover trees only after stamp (ADR 0026).

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
python -m harness.cli.main fold --report data/reports/fold.json
# Default is dry-run. --apply only after harvest stamp, on VTA, Vince present.
# Never hides Vince Personal. Never archives 00-06 (archived SPO drops out of Copilot).
```

Leftover personal-OneDrive / old Petra OneDrive / a second real Downloads /
laptop leftovers (report-only inventory; no copy or upload). VTA Desktop,
Documents, and Downloads already redirect into `00_Inbox/_from_*`. Pass the
roots that still sit outside Vince Personal on the machine you are standing at.
Laptop stays query-only for digest/drain; inventory is safe there because it
does not mutate:

```powershell
python -m harness.cli.main inventory --report data/reports/inventory.json --root "C:\Users\vince\OneDrive" --root "C:\Users\vince\Downloads"
python -m harness.cli.main inventory --report data/reports/inventory.json --roots-file config/inventory_roots.example.yaml
```

Hits classify as `candidate-to-consume`, `skip-code`, `skip-secret`, or
`already-in-VincePersonal`. Code trees, secrets, and
`C:\Users\vince\local-inference-canonical` stay off SharePoint. Files already
under the Vince Personal sync root are `already-in-VincePersonal` — never hide
that library. Do not run those Windows paths from a Cloud Agent VM.

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
