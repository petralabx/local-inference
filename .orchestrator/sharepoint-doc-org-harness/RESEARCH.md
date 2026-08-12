---
slug: sharepoint-doc-org-harness
created: 2026-08-12T11:10:00Z
status: consumed-by-spec
rubric_score: 91
---

# RESEARCH — SharePoint Document Organization Harness

## Mission and Context

Build a first-class durable harness that keeps Vince’s files and Outlook mail
organized on **VincePersonal SharePoint only**, with wide-auto daily digest,
historical cleanup to a research-chosen horizon, easy reverse, and
knowledge-graph provenance. Local Qwen / Ornith judgment runs only through the
Dell LiteLLM proxy after build (no paid tokens). Success order: provenance
queries → inbox drain → near-zero drift.

**Retain:** `00_Inbox`–`06_Reference` taxonomy, naming shape
`YYYY-MM-DD_PREFIX_Description_vNN.ext`, `correction_rules.json` as seed
routing signal, prior undo logs / reports as evidence.

**Replace:** Claude Cowork scheduled `SKILL.md` runtime, copy-then-version-bump
inbox behavior, filename-keyword-only classification as the primary path.

**Constraints**

- SharePoint VincePersonal is SoT (not OneDrive personal library, not Paperless).
- Hosts: Dell-VTA (scheduler / worker) + laptop `taylorvalton` (same SoT).
- Wide auto with reverse + KG provenance; deletes stay reverse-safe.
- Email: Outlook folders/rules **and** attachments filed into VincePersonal.
- Exclude code/repos (`agentic-swarm`, `node_modules`, git trees) from filing.
- Prefer OSS wrap over greenfield.
- Execution is **not** authorized by this research brief.

**Research-owned historical horizon (decision)**

Use **12 months** as the active reorg horizon. That matches the August 2026
health report’s “stale (12+ mo)” metric (~19k files) and Vince’s ~1 year float.
Files older than 12 months (by last-modified, falling back to created) get
archive-in-place under the nearest `_Archive/` only — no rename/classify churn
except graph-confirmed byte-identical dedupe. Inbox backlog older than 12 months
goes to an archive-triage lane first; content-classify the ≤12-month slice first.

**Inbox ceiling (working target for later spec)**

Prior stuck inbox ≈ 2,064. Working ceiling after harness cutover: **≤ 100**
active (non-archive-triage) items in `00_Inbox` + `_Unsorted_Imports` top-level,
measured after daily digest.

## Internal Findings

### local-inference is the inference contract, not the product home

- `litellm/config.yaml` exposes `local-primary`, `local-fast` (Qwen3-32B-AWQ on
  Dell), `local-coder` (Ornith on Spark A), `local-driver` (Qwen3.6-A3B on Spark
  B). Clients must call `http://100.103.33.54:4000/v1`, never Spark `:8000`.
- This repo’s roots (`scripts/`, `litellm/`, `docs/`, `.cursor/`) are LiteLLM /
  DGX fleet tooling. A document-org harness does **not** belong as product code
  here without a costed migration that would blur repo purpose.

**Recommended home repo:** new governed repo
`petralabx/sharepoint-doc-org-harness` (Python worker + CLI + tests +
Task Scheduler / systemd-equivalent jobs). Keep discovery/orchestrator scratch in
the current workspace if useful, but ship the harness outside
`local-inference`. Thin hooks may later land in `agentic-swarm` (skill /
`m365_auto` prompt updates) without owning the runtime.

### Prior Claude / Cowork harness (failing control plane)

Live project path (personal OneDrive, **not** VincePersonal SharePoint):

`C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd\07_Admin\Documents\Claude\Projects\Organize all my current files + automate future organization\`

Evidence read:

- `File_Organization_Project_Plan.md` (2026-05-09): SharePoint-only SoT,
  taxonomy, prefix table, metadata columns, five automations.
- `inbox_sorter_log_2026-08-12.md`: 511 scanned → **1** sorted, **508** held;
  sorter **copies** and version-bumps → runaway `_vNN` duplicates (A1: 54 files /
  17 unique). Keyword classification fails on coded names (`IN…`, `QT…`).
- `health_report_2026-08.md`: ~42.6k files / ~62 GB in `00`–`06`; inbox ~2,064;
  naming compliance ~27%; 1,289 duplicate-named; 19,394 stale 12+ mo outside
  `_Archive`; PLX client subtree and `*_Old` folders dominate non-compliance.
- `correction_rules.json`: only **5** filename-keyword rules (Trafilea, Gleamin,
  Warehouse Responsibilities, Email Categorization Rules, Tractor Supply) — useful
  seed, insufficient as primary classifier.
- Large CSV undo logs already exist (`migration_undo_log.csv`,
  `Rename_Undo_Log.csv`, consolidation undo logs) — pattern to harden into a
  first-class reverse journal, not abandon.
- Outlook setup scripts already exist in the project folder
  (`Setup_Outlook_Folders.ps1`, `Setup_Outlook_Rules.ps1`,
  `Save-Attachments-To-Inbox.ps1`) — reuse intent, not Cowork scheduling.
- Scheduled Cowork folder
  `...\07_Admin\Documents\Claude\Scheduled` exists but listed empty / likely
  cloud-only from this session; discovery still documents the six SKILL jobs.

Discovery path bug: ledger said `...\07_Admin\...` under VincePersonal sync
root; actual Claude project lives under **personal OneDrive** `07_Admin`, while
corpus SoT is
`...\Vince Personal - Documents` (SharePoint sync). Confirmed taxonomy folders
`00_Inbox`…`06_Reference` plus leftover root folders on the SharePoint sync root.

### agentic-swarm / M365 patterns to reuse

- `prompts/plx/m365_auto.md`: VincePersonal as SoT; naming convention; 180-day
  archive policy (superseded for this harness by the 12-month horizon above for
  *active reorg*; archive-in-place still applies).
- `skills/plx/document-management.md`: SharePoint ingest → classify → Docling
  extract → file; already names Paperless-ngx (pattern) and Docling (tool).
- `config/kb-contract.yaml`: SharePoint VincePersonal is a KB source type;
  email ingest exists but compile_enabled false — PLX Brain indexes SP docs
  today (brain_search returned VincePersonal paths) but is **document search**,
  not move/rename provenance.
- `config/execution-primitives.yaml` `graph_api`: PLX_Forms app-only is
  **read-biased** for SharePoint writes. Live `user-ms365` verify-login returned
  app-only. Harness mutations and Outlook rules need **delegated** (user) Graph
  auth or sync-root filesystem ops under Vince’s OneDrive client, not app-only
  alone.

### Cross-machine / ops

- Same SharePoint library syncs on VTA and laptop → SoT consistency is cloud-side.
- Scheduler should be **single-writer on Dell-VTA** to avoid dual-machine races;
  laptop is consumer + ad-hoc agent client.
- PLX Brain remains optional secondary index for content search; harness-local
  provenance graph is required for “where did file X go?” under wide auto.

## External Findings

### Document extract / OCR

- **Docling** (MIT, ~65k★): local PDF/Office → structured markdown/JSON; Windows
  supported; pairs with local LLMs; PLX skill already cites it. Best primary
  extract layer for content classification without cloud OCR APIs.
- **OCRmyPDF** (MPL-2.0, ~34k★): searchable PDF text layer; native Windows via
  Python + Tesseract + Ghostscript. Use only for scan/image PDFs Docling cannot
  read well — not a full DMS.

### DMS patterns (not SoT)

- **Paperless-ngx** (GPL-3.0, ~44k★): mature ingest/tag/classify/archive patterns
  (consume folder, OCR worker, ML tags). It wants to **own** the archive. No
  native SharePoint SoT. Adopt patterns; do **not** deploy as SoT. GPL is fine
  for internal self-host but SoT conflict dominates.

### Dedup

- **fclones** (MIT, ~2.9k★): fast content-hash groups; JSON/CSV; Windows works
  (shell glob caveats). Best wrap for byte-identical duplicate plans.
- **rdfind** (GPL-style “Other”, ~1.3k★): mature on Unix; Windows via Cygwin —
  weaker Windows fit than fclones. Keep as reference; prefer fclones.

### Microsoft Graph

- **msgraph-sdk-python** (MIT): official SharePoint drive + mail APIs; Windows
  long-path note. Correct library for Graph-backed moves, mail folder ops,
  attachment extract. Needs delegated credentials for write/mail.
- **msgraph-sdk-dotnet** (Microsoft license / Other on GitHub): viable if a
  Windows-native host wins; Python stack aligns better with Docling + LiteLLM.

### Filesystem / metadata

- **fsspec** (BSD-3): useful I/O abstraction; do not force a Graph drive adapter
  if OneDrive sync root is the primary mutate path — optional layer.
- **Apache Tika** (Apache-2.0): broad MIME/metadata; JVM weight. Prefer Docling
  first; keep Tika as fallback for exotic types Docling skips.

### Provenance graph

- **Neo4j Community** (GPL-3.0): durable Cypher “where did it go?” queries;
  Docker on VTA is the practical Windows host. Heavier ops, strongest agent UX.
- **Memgraph** (BSL / Other): Cypher-compatible, lighter runtime, weaker license
  posture for a long-lived personal harness — reject as primary.
- **Kuzu** (MIT, archived upstream after acquisition): embedded Cypher was
  attractive; **reject as primary** due to archived upstream / fork risk.
- **NetworkX** (BSD-3): great in-process graph math; not durable alone. Pair with
  an append-only SQLite action journal if Neo4j ops cost is deferred.
- Better pattern: **SQLite event journal = reverse SoT**; graph DB = query
  projection rebuilt/updated from the journal.

### Vectors / tagging UX

- **Qdrant** (Apache-2.0): strong local vector DB; Docker preferred; optional
  semantic recall — not required for provenance-first success.
- **LanceDB** (Apache-2.0): embedded local vectors; better Windows/Python fit if
  semantic search is added later. Prefer LanceDB over Qdrant for phase-1 optional
  search to avoid another server.
- **TagSpaces** (AGPL-3.0): offline tagging UX ideas only; AGPL + not SharePoint
  SoT → reject as runtime.
- **Karakeep** (AGPL-3.0): bookmark/AI-tag patterns; wrong domain (bookmarks vs
  SP library) and AGPL → reject as runtime; mine tagging UX ideas only.

### Local-LLM fit

- Docling + LiteLLM-compatible classify/rename prompts map cleanly to
  `local-primary` / `local-fast` for batch triage; `local-coder` /
  `local-driver` reserved for harness code / agent tooling, not bulk classify.
- Steady-state must not call OpenAI/Anthropic; keep model base URL pinned to the
  Dell proxy.

## Candidate Approaches

### Approach 1 - VTA Python harness, SharePoint SoT, OSS wrap stack

Single-writer Python service on Dell-VTA. Mutate via OneDrive sync root for bulk
FS ops **and/or** delegated Graph for mail + cloud-authoritative moves. Pipeline:
scope filter → content-hash identity → Docling(+OCRmyPDF) extract → local-LLM
classify/rename → move (not copy) with SQLite reverse journal → provenance graph
update → daily digest. Dedup via fclones. Historical lane archives >12 months
in-place. Agents query provenance via Cypher/API.

- Pros: Meets SoT, reverse, KG, local-LLM, email+files, OSS-first; kills Cowork
  duplication root cause; reuses taxonomy/corrections/undo evidence.
- Cons: Requires building orchestration glue; Graph delegated auth work; dual
  path (sync FS vs Graph) must be designed carefully for races.
- Risk: Medium — wide auto on ~43k files; mitigated by journaled reverse +
  content-hash identity + exclude lists.
- Effort: L (multi-week; ingest/classify/dedupe/provenance/email/jobs/tests).
- Blast Radius: VincePersonal library + Outlook personal mailbox; Dell-VTA
  scheduler; LiteLLM load for classify; optional Neo4j Docker on VTA. No change
  to local-inference product roots beyond consumption of the proxy.

### Approach 2 - Paperless-ngx as processing hub, mirror to SharePoint

Deploy Paperless-ngx; consume inbox into Paperless; sync/export into SharePoint
folders. Use Paperless tags/ML as classifier.

- Pros: Fastest “DMS features” (OCR, tags, consume folder); less custom UI.
- Cons: Violates SharePoint-as-SoT unless carefully demoted to cache; dual truth
  and drift risk; GPL stack + Docker ops; weak Outlook folder/rules story;
  reverse/KG still custom.
- Risk: High — SoT split recreates the failure mode discovery forbids.
- Effort: M–L (deploy + sync bridge + still custom provenance).
- Blast Radius: New Docker stack on VTA; possible second corpus copy; sync
  conflicts with OneDrive client.

### Approach 3 - Power Automate / Graph-only cloud control plane + LLM sidecar

Cloud flows for Outlook rules, attachment save, SharePoint moves; local worker
only for LLM classify calls.

- Pros: Native M365 surfaces; less Windows service code; mail rules fit well.
- Cons: Hard to get first-class reverse journal + KG; flow limits/complexity;
  local-LLM integration awkward; wide-auto historical cleanup poor; vendor lock
  to Power Platform; Cowork-shaped fragility risk.
- Risk: High for provenance-first success criterion.
- Effort: M (flows) + M (sidecar) with ongoing flow debt.
- Blast Radius: Tenant Power Platform; Graph permissions; weaker local testability.

## Recommendation

Chosen approach: **Approach 1 - VTA Python harness, SharePoint SoT, OSS wrap stack**

Why this wins:

- Keeps VincePersonal as the only file SoT and replaces the Cowork control plane
  with a repo-owned, testable worker.
- Directly fixes the proven failure mode (copy + keyword-only) with move +
  content extract + local-LLM classify + content-hash identity.
- Delivers provenance-first success via SQLite reverse journal + queryable graph
  projection (Neo4j Community preferred; NetworkX rebuild acceptable as
  phase-0).
- Maximizes OSS wrap (Docling, OCRmyPDF, fclones, msgraph-sdk-python) and keeps
  steady-state inference on Dell LiteLLM only.
- Email and attachments fit Graph delegated APIs; files can use sync-root for
  bulk hash/dedupe without abandoning SharePoint identity.

What could change this decision:

- If delegated Graph write/mail auth is blocked by tenant policy, lean harder on
  sync-root FS mutations + Outlook COM/Graph hybrid and re-score Approach 3 for
  mail-only.
- If Vince insists on zero Docker on VTA, drop Neo4j server and use SQLite +
  NetworkX projection only (still Approach 1 architecture).

**Lane split (post-build, local only)**

| Lane | Alias | Job |
|------|-------|-----|
| Batch classify / rename suggest | `local-fast` / `local-primary` | Document + mail triage |
| Harness code / agent tooling | `local-coder` / `local-driver` | Spec/build agents, not bulk filing |
| Never | paid cloud APIs | Steady-state classify/digest/provenance |

**Home host:** Dell-VTA single-writer scheduler; laptop reads SoT + runs ad-hoc
agent queries against the same graph/API.

## Open Questions

1. Delegated Graph app registration: user-consent scopes for
   `Files.ReadWrite`, `Mail.ReadWrite`, mailbox identity
   (`vince@petrasoap.com` assumed) — confirm exact UPN and app ownership.
2. Mutate path priority: sync-root FS first vs Graph drive item APIs first for
   SharePoint moves (recommend: Graph for authoritative item IDs when online;
   FS for hash/dedupe scans).
3. Delete policy confirmation: auto-delete only graph-confirmed byte-identical
   duplicates with tombstone (assumption from discovery) — Vince still owns
   final say.
4. PLX Brain: keep as secondary content index only, or also mirror provenance
   edges? (Recommend secondary only in phase 1.)
5. Neo4j Docker on VTA vs SQLite+NetworkX phase-0: pick in spec based on Vince
   Docker appetite.
6. Numeric inbox ceiling (proposed ≤100) — accept or adjust in Stage 1 spec.
7. Whether leftover root folders (`artifacts`, `Command Center`, `PLX.io`, …)
   stay out of naming enforcement forever or get a later migration lane.

## Sources

### Internal

- `.discovery/sharepoint-doc-org-harness/DISCOVERY.md` (approved mission, lenses,
  OSS mandate, handoff to candidate `sha256-0f053485…`)
- `.discovery/sharepoint-doc-org-harness/candidates/sha256-0f053485230e80ef881c98f39430074a4e1e676412cf7381547f19c747e97902/CANDIDATE.md`
- `litellm/config.yaml` (local model aliases / proxy contract)
- `docs/runbooks/dgx-spark-fleet.md` (proxy URL; never hit Spark `:8000`)
- Claude project:
  `...\07_Admin\Documents\Claude\Projects\Organize all my current files + automate future organization\`
  (`File_Organization_Project_Plan.md`, `inbox_sorter_log_2026-08-12.md`,
  `health_report_2026-08.md`, `correction_rules.json`, `Session_Handoff.md`,
  undo CSVs, Outlook setup scripts)
- SharePoint sync root:
  `...\Vince Personal - Documents` (taxonomy folders present; inbox ~2063 files)
- `C:\Users\vince\agentic-swarm\prompts\plx\m365_auto.md`
- `C:\Users\vince\agentic-swarm\skills\plx\document-management.md`
- `C:\Users\vince\agentic-swarm\config\kb-contract.yaml`
- `C:\Users\vince\agentic-swarm\config\execution-primitives.yaml` (app-only
  Graph read bias)
- PLX Brain `brain_search` (VincePersonal SharePoint documents indexed; not
  move provenance)
- MS365 MCP `verify-login` (app-only session in this research environment)

### External

- https://github.com/docling-project/docling (MIT; local extract; Windows)
- https://github.com/docling-project/docling-graph (LiteLLM-local extract→graph
  patterns; optional later)
- https://github.com/ocrmypdf/OCRmyPDF (MPL-2.0; Windows OCR layer)
- https://github.com/paperless-ngx/paperless-ngx (GPL-3.0; ingest patterns; not SoT)
- https://github.com/pkolaczk/fclones (MIT; Windows-capable dedupe)
- https://github.com/pauldreik/rdfind (Unix-first dedupe)
- https://github.com/microsoftgraph/msgraph-sdk-python (MIT; Graph SP + mail)
- https://github.com/microsoftgraph/msgraph-sdk-dotnet (.NET Graph SDK)
- https://github.com/fsspec/filesystem_spec (BSD-3)
- https://github.com/apache/tika (Apache-2.0)
- https://github.com/neo4j/neo4j (GPL-3.0 Community)
- https://github.com/memgraph/memgraph (BSL/Other)
- https://github.com/kuzudb/kuzu (MIT; archived upstream — reject primary)
- https://github.com/qdrant/qdrant (Apache-2.0)
- https://github.com/lancedb/lancedb (Apache-2.0; embedded local vectors)
- https://github.com/tagspaces/tagspaces (AGPL-3.0)
- https://github.com/karakeep-app/karakeep (AGPL-3.0)
- https://networkx.org/documentation/stable/ (BSD-3; in-process graph)
- https://learn.microsoft.com/en-us/graph/sdks/sdks-overview

## OSS adopt / wrap / reject table

Decision key: **adopt** = ship/run as dependency; **wrap** = call as subprocess
or library behind harness interfaces; **reject** = do not run as part of the
harness (patterns may still inform design).

| Repo | License | Stars (approx) | Windows fit | SharePoint SoT fit | Local-LLM fit | Decision | Rationale |
|------|---------|----------------|-------------|--------------------|---------------|----------|-----------|
| docling-project/docling | MIT | ~65k | Good (Win/macOS/Linux) | High — extract only; files stay on SP | Excellent — structured text for LiteLLM classify | **Adopt / wrap** | Primary content extract; already in PLX document-management skill |
| ocrmypdf/OCRmyPDF | MPL-2.0 | ~34k | Good (native + Tesseract/GS) | High — optional PDF text layer on SP copies/paths | Good — improves extract quality; no cloud OCR | **Wrap** | Scan/image PDF lane only; not a DMS |
| paperless-ngx/paperless-ngx | GPL-3.0 | ~44k | Docker/WSL-centric | **Poor as SoT** — wants own archive | Partial (own ML; can point to local models with work) | **Reject (runtime)** / **adopt patterns** | Mine consume-folder + tag/archive patterns; never dual-SoT |
| pkolaczk/fclones | MIT | ~2.9k | Good (shell glob caveats) | High — hash groups over sync root / exports | N/A | **Wrap** | Primary byte-identical dedupe engine; JSON/CSV into journal |
| pauldreik/rdfind | Other (GPL-style) | ~1.3k | Weak (Cygwin) | High in principle | N/A | **Reject (primary)** | Prefer fclones on Windows; keep as algorithm reference |
| microsoftgraph/msgraph-sdk-python | MIT | ~0.6k | Good (enable long paths) | **Required** for Graph mail + drive item IDs | N/A (transport) | **Adopt** | Official SP + Outlook API surface; needs delegated auth |
| microsoftgraph/msgraph-sdk-dotnet | Other (MS) | ~0.8k | Excellent | High | N/A | **Reject (primary)** | Python stack wins for Docling/LiteLLM unless .NET host is mandated later |
| fsspec/filesystem_spec | BSD-3 | ~1.3k | Good | Neutral — abstraction only | N/A | **Wrap (optional)** | Use if multi-backend I/O helps; not mandatory if sync root + Graph SDK suffice |
| apache/tika | Apache-2.0 | ~4.0k | JVM/Docker | High as sidecar | Indirect | **Wrap (fallback)** | Exotic MIME/metadata when Docling skips; avoid as default path |
| neo4j/neo4j | GPL-3.0 (Community) | ~17k | Docker on VTA | High — graph of SP item IDs/paths/hashes | Excellent for agent Cypher provenance | **Wrap (preferred KG)** | Provenance query surface; journal remains reverse SoT |
| memgraph/memgraph | BSL / Other | ~4.3k | Docker | High | Good | **Reject (primary)** | License/ops trade-off worse than Neo4j Community for this use |
| qdrant/qdrant | Apache-2.0 | ~34k | Docker/WSL | Optional semantic index only | Good with local embeddings | **Reject (phase 1)** | Not needed for provenance-first success; revisit if semantic search required |
| lancedb/lancedb | Apache-2.0 | ~11k | Excellent (embedded) | Optional index only | Good | **Wrap (optional phase 2)** | Prefer over Qdrant if vectors are added; still secondary to KG |
| tagspaces/tagspaces | AGPL-3.0 | ~5.2k | Desktop app | Poor — parallel UX, not SP SoT | Partial | **Reject** | Mine tag UX ideas only; AGPL + SoT conflict |
| karakeep-app/karakeep | AGPL-3.0 | ~28k | Docker | Poor — bookmarks domain | Often cloud/local mix | **Reject** | Wrong problem shape; AGPL |

### Better finds (not in seed list)

| Repo / tech | License | Decision | Rationale |
|-------------|---------|----------|-----------|
| networkx/networkx | BSD-3 | **Wrap (phase-0 / fallback KG)** | In-process provenance queries rebuilt from SQLite journal if Neo4j deferred |
| docling-project/docling-graph | MIT | **Watch / optional later** | LiteLLM-routed extract→graph; overlaps harness KG — do not adopt until core journal exists |
| kuzudb/kuzu | MIT | **Reject (primary)** | Embedded Cypher attractive but upstream archived; fork risk |
| Existing Claude undo CSVs + Outlook setup PS1 | n/a (internal) | **Adopt as seed artifacts** | Schema inspiration for reverse journal + mail folder bootstrap |

### Top wrap stack (phase 1)

1. **msgraph-sdk-python** — mail + authoritative drive identity  
2. **docling** — content extract for classify  
3. **fclones** — byte-identical dedupe groups  
4. **OCRmyPDF** — scan PDF text layer  
5. **Neo4j Community (or NetworkX+SQLite)** — provenance queries; SQLite journal for reverse  

## Rubric scorecard (iteration 1)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Mission + constraints | 15 | 14 | Horizon + ceiling proposed; delete policy still Vince-owned |
| Internal findings | 20 | 18 | Mapped LI, swarm, live Claude project, auth gap, home-repo call |
| External findings | 15 | 14 | Seeded OSS deepened; Kuzu/NetworkX/docling-graph noted |
| Candidate approaches | 25 | 23 | Three options with pros/cons/risk/effort/blast-radius |
| Recommendation | 15 | 14 | Clear Approach 1; change triggers listed |
| Contradictions + OQ | 5 | 4 | Sync vs Graph mutate path + auth called out |
| Source traceability | 5 | 5 | Internal paths + GitHub/docs linked |
| **Total** | **100** | **91** | Pass threshold (≥85); status remains `draft` pending orchestrator Stage 1 |

Control arm: no prior `RESEARCH.md` existed for this slug; baseline treated as empty
brief (score 0). Net improvement material. Fixpoint not claimed — single research
pass for Stages 0–3.

## Handoff notes (non-claims)

- This artifact is research only. It does **not** authorize execution, create a
  SPEC, or mint product code.
- Next spine step: `project-orchestrator` Stages 1–2 consume this brief into
  `SPEC.md` for Vince approval; Stage 3+ only after separate execution
  authorization.
