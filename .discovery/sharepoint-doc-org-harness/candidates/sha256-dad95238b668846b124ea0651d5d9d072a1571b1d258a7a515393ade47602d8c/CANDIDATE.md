---
slug: sharepoint-doc-org-harness
created: 2026-08-12T10:35:00Z
updated: 2026-08-12T11:00:00Z
status: in-review
mode: research+plan+execute
lens_cursor: done
---

# Discovery — SharePoint Document Organization Harness

## Mission

Clean up Vince's documents and emails and build a first-class, durable harness so
folders, files, mail, location, naming, meta-tags, and versioning stay organized
across Dell-VTA and the Dell laptop `taylorvalton`, with SharePoint as the only
file system of record. Reuse useful parts of the existing Claude/Cowork corpus
and taxonomy; replace the Cowork control plane. Local Qwen / Ornith lanes (via
Dell LiteLLM) plus agents run wide-auto daily digest, historical cleanup, graph
indexing, and ad-hoc provenance queries, with an easy reverse path.

## Lenses

| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1 | Outcome | yes | answered | 2026-08-12T10:40:00Z |
| L2 | Users and jobs | yes | answered | 2026-08-12T10:50:00Z |
| L3 | Current reality | yes | prefilled | 2026-08-12T10:35:00Z |
| L4 | Constraints | yes | prefilled | 2026-08-12T10:50:00Z |
| L5 | Blast radius | yes | answered | 2026-08-12T10:45:00Z |
| L6 | Success evidence | yes | answered | 2026-08-12T10:48:00Z |
| L7 | Non-goals | yes | answered | 2026-08-12T10:53:00Z |
| L8 | Stakeholders | yes | answered | 2026-08-12T10:55:00Z |
| L9 | Alternatives | no | prefilled | 2026-08-12T10:35:00Z |
| L10 | Timing | no | waived | — |
| L11 | Operations | no | prefilled | 2026-08-12T10:55:00Z |
| L12 | Taste | no | waived | — |

## Answers

### L1 — Outcome

Build a **new first-class durable harness** (not a patch of Claude Cowork).
Success means documents stay organized without depending on Claude Projects as
the control plane, both machines see the same SharePoint truth, and local Qwen /
Ornith lanes do the judgment work the keyword rules could not.

**Retain from what exists (agent recommendation, Vince defaulted to agent):**

- Keep VincePersonal SharePoint as SoT and the `00_Inbox`–`06_Reference` taxonomy
  as the starting information architecture (fix folders later, do not re-migrate
  the whole corpus from scratch).
- Keep the naming convention shape
  `YYYY-MM-DD_PREFIX_Description_vNN.ext` and the prefix table as a baseline.
- Keep `correction_rules.json` as seed training signal for learned routing.
- Keep migration undo logs / prior reports as evidence for dedupe and scope
  exclusions (code trees, `node_modules`, desktop junk).

**Discard / replace:**

- Claude Cowork scheduled `SKILL.md` jobs as the runtime.
- Copy-then-version-bump inbox behavior (must be move or manifest-idempotent).
- Filename-keyword-only classification as the primary path.
- Scanning repo/`node_modules` trees for naming compliance.

Kill criterion (stated by Vince as "default to agent"): if the new harness is not
first-class and durable — i.e. another prompt folder that drifts and re-duplicates
files — stop and redesign rather than ship a Claude-shaped clone.

### L5 — Blast radius

**Wide auto.** Gated crawl / walk / run failed with Claude Code; do not repeat
that operating model. The harness may auto-move, rename, archive, and apply
rename/dedupe plans without per-batch human approval.

Hard requirements that make wide auto acceptable:

1. **Easy reverse** — every write path must support a simple reverse function that
   can undo harness actions (stronger than "SharePoint version history alone").
2. **Knowledge-graph provenance** — a strong graph of file identity and moves so
   Vince (or an agent) can ask where a file went after it was renamed/reorganized
   and get a trustworthy answer.

Deletes remain the highest-risk action; treat them as reverse-safe and
graph-logged even under wide auto (exact delete policy still open — see
Assumptions).

### L2 — Users and jobs

**Primary operators:** Vince plus any agent that can use his local models and
usefully keep files/emails organized, meta-tagged, and graph-indexed. Design
should assume a multi-agent operator surface, not a Vince-only CLI.

**Standing jobs:**

1. **Daily automatic digest** of new and pending items (inbox files and email
   organization in scope).
2. **Historical cleanup** of the existing mess to a horizon research will set
   (Vince floated ~1 year; not fixed — research chooses the appropriate cutoff).
3. **Ad-hoc agent functions** as needed for a world-class durable system
   (provenance queries, drift checks, reverse, meta-tag repair) — not limited to
   a single chat persona.

Frequency: daily automation is mandatory; ad-hoc agent use is on demand.

### L6 — Success evidence

Priority order (Vince):

1. **Provenance first** — agent (or Vince) can resolve “where is the file that
   used to be named X / lived at path Y?” for real examples without hand-reading
   raw logs. This is the primary proof the harness is trustworthy under wide auto.
2. **Inbox drains** — `00_Inbox` (incl. `_Unsorted_Imports`) falls and stays
   under a working ceiling across ongoing wide-auto runs (numeric ceiling still
   open; prior corpus was ~2k stuck).
3. **Near-zero drift** — files stay consistently and correctly organized after
   the initial cleanup; the system does not re-create sprawl, duplicate `_vNN`
   stacks, or fragmented client folders.

Secondary (still valuable, not the ranking Vince gave): no re-duplication and
one-command reverse remain design requirements from L5, not demoted.

### L3 — Current reality

Prefilled from the Claude project that was open in Cursor history and from the
scheduled Cowork skills.

**Canonical corpus today**

- Personal SharePoint site: `https://petrasoap.sharepoint.com/sites/VincePersonal/Shared%20Documents/`
- Local sync root (OneDrive client mapping SharePoint):  
  `C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd\Vince Personal - Documents`
- Folder taxonomy already exists: `00_Inbox` … `06_Reference` plus leftover root
  folders (`artifacts`, `Automation Logs`, `Command Center`, `General`, `PLX.io`,
  `Projects`, `Shared Documents`, etc.).
- Claude project knowledge + emits live under:  
  `...\07_Admin\Documents\Claude\Projects\Organize all my current files + automate future organization\`
- Scheduled Cowork prompts (the harness "prompt" side):  
  `...\07_Admin\Documents\Claude\Scheduled\{daily-inbox-sorter,daily-correction-detector,weekly-name-enforcer,weekly-duplicate-finder,monthly-stale-archiver,monthly-health-report}\SKILL.md`

**What already ran**

- `File_Organization_Project_Plan.md` (2026-05-09) defined SharePoint-only
  architecture, taxonomy, `YYYY-MM-DD_PREFIX_Description_v01.ext`, metadata
  columns, and five automations.
- Migration claimed ~30k of ~36k files copied into the new structure (~84%),
  with remaining cloud-only Dropbox photos stuck.
- Five scheduled jobs emit daily/weekly/monthly markdown reports into the Claude
  project folder (the "emit" side the user had open).

**Why it is failing (from today's emits)**

- `inbox_sorter_log_2026-08-12.md`: of 511 inbox files scanned, **1** sorted;
  **508** held. Sorter **copies** instead of moves, so the same file reappears as
  new `_vNN` duplicates every run (A1 folder: 54 files / 17 unique). Client
  folders are fragmented (`Spa_Dr` / `SpaDr` / `SpaDoctor`, etc.). Classification
  is keyword-on-filename; coded names (`IN3000048765.pdf`, `QT…`) never match.
- `name_enforcer_report_2026-08-12.md`: **38%** compliance over 30,491 scanned
  files; top offenders include product photos and **code/repo trees**
  (`agentic-swarm`, `node_modules`) that should be out of scope.
- `health_report_2026-08.md`: ~42.6k files / ~62 GB in `00`–`06`; inbox stuck at
  ~2,064; naming compliance plateaued ~27% when inbox is included; 1,289
  duplicate-named files; stale files outside `_Archive` still rising.

**Cross-machine**

- Intent: same SharePoint SoT on Dell-VTA and laptop `taylorvalton`.
- Evidence of laptop-specific local sprawl not yet audited in this discovery pass.

### L4 — Constraints

Prefilled from user intake + plan docs + L1 answer.

- Canonical store must be **SharePoint**, not OneDrive personal library as SoT.
  (Open tension: current access path is OneDrive sync of the SharePoint library.)
- Must work on **Dell-VTA** and **Dell laptop taylorvalton**.
- Harness must be **first-class and durable** (repo-owned or equivalent operator
  surface with logs, idempotency, tests — not a Claude Projects folder).
- Must **leverage DGX / local models** via the Dell LiteLLM proxy
  (`http://100.103.33.54:4000/v1`). Current aliases in
  `local-inference` `litellm/config.yaml`: `local-primary` / `local-fast` (Qwen3
  on Dell), `local-coder` (Ornith-35B on Spark A), `local-driver` (Qwen3.6-A3B on
  Spark B). Exact lane split (classify vs rename suggest vs batch triage) still
  open.
- Prior Claude Projects / Cowork approach is not the control plane going forward.
- Wide automation is required; gated approve-every-batch is a non-goal.
- Every mutating action must be reverseable via an easy reverse function.
- Provenance must land in a **knowledge graph** queryable by agents (where did
  file X go / what was it renamed to?). Existing PLX Brain MCP is a candidate
  substrate, not yet chosen.
- Scope includes **email**: Outlook folders/rules **and** attachments filed to
  SharePoint (VincePersonal). Mailbox identity assumed `vince@petrasoap.com`
  until corrected.
- Daily digest is mandatory; historical cleanup horizon is research-owned
  (~1 year suggested). Older than horizon → archive in place / cold archive,
  not active churn.
- Filing scope is **VincePersonal only**; exclude code/repo trees from
  naming/filing automation.
- **Zero paid inference after build:** steady-state harness runs and the agents
  that maintain the system must use **local model lanes only** via the Dell
  LiteLLM proxy. No cloud API token spend (OpenAI/Anthropic/etc.) for
  classification, digest, provenance answers, or ongoing maintenance. Discovery
  / one-time build planning may still use frontier models in Cursor; runtime
  must not.
- Destructive deletes under wide auto: unresolved after L6. Assumption until
  answered: auto-delete only for graph-confirmed byte-identical duplicates with
  reverse + tombstone in the knowledge graph; all other deletes human-triggered.
  Owner: Vince.

### L7 — Non-goals

Vince confirmed:

- **Exclude** code/repos from naming/filing (`agentic-swarm`, `node_modules`, git
  working trees, similar).
- **Email in scope as both** Outlook folder/rules organization **and** filing
  attachments into SharePoint.
- **VincePersonal only** — not Petra team SharePoint sites.
- **Historical age floor:** beyond the research-chosen horizon (~1 year
  suggested), do not churn; **archive** so Vince knows where to look if needed.

Still out from earlier decisions:

- OneDrive as system of record.
- Claude Projects / Cowork as long-term control plane.
- Blind full re-migration / full taxonomy reset.
- Gated crawl/walk/run as steady-state safety model.

### L8 — Stakeholders

**Vince (Vinny Sachet) only** as required approver and sole review authority for
Stage 4. No consulted human required. Agents operate under Vince; they do not
approve.

### L9 — Alternatives

Tried: Claude Projects / Cowork with scheduled SKILL.md jobs writing markdown
emits (inbox sorter, name enforcer, duplicate finder, stale archiver, health
report). Rejected as ineffective by the user. Earlier OneDrive-root cleanup
(2026-03) and M365 Auto / VincePersonal policies also exist in swarm docs.

### L11 — Operations

Today's ops surface is Claude Cowork scheduled skills + PowerShell migration
scripts + markdown/CSV logs in the Claude project folder. Target ops surface
(from L1/L5/L2): durable harness with wide auto, daily digest, reverse entry,
agent-queryable knowledge graph, Outlook + SharePoint attachment filing.
Home host (VTA as scheduler vs dual-machine) left for research.

## Assumptions

- "Version controls" means harness-code versioning in git plus file provenance in
  the knowledge graph; filename `_vNN` and SharePoint versions are secondary.
  Owner: Vince (confirm).
- The VincePersonal SharePoint site remains the personal SoT; team/shared Petra
  sites are secondary. Owner: Vince.
- Knowledge-graph substrate may be PLX Brain, a harness-local graph, or both —
  not chosen. Owner: discovery / research mode.
- MC fuzzy candidates (TASK-267 / 308 / 458) are portal/infra noise and are not
  linked to this discovery. Owner: Vince / COS.

## Non-Goals

- OneDrive as canonical document store.
- Claude Projects / Cowork as the permanent control plane.
- Blind full re-migration of the already-copied SharePoint corpus.
- Gated crawl/walk/run as the steady-state safety model.
- Naming/filing automation over code repos, `node_modules`, git working trees.
- Petra team SharePoint sites (VincePersonal only).
- Active churn of material older than the research-chosen historical horizon
  (archive so it remains findable; do not endlessly reorganize decades of files).
- Paid / cloud LLM tokens for steady-state maintenance or agent operation after
  the harness is built.

## Evidence

- Cursor editor history workspace `958df74c…` had open:  
  `name_enforcer_report_2026-08-12.md`, `inbox_sorter_log_2026-08-12.md`,
  `duplicate_finder_report_2026-08-05.md` under the Claude project folder.
- Read: `File_Organization_Project_Plan.md`, `Session_Handoff.md`,
  `daily-inbox-sorter/SKILL.md`, `weekly-name-enforcer/SKILL.md`,
  `health_report_2026-08.md`, today's name-enforcer + inbox-sorter emits.
- Related prior art in swarm: `prompts/plx/m365_auto.md`, `docs/FILE_AUDIT.md`,
  `skills/plx/document-management.md` (VincePersonal SoT + naming convention).
- PLX_MC SharePoint integration docs describe MC lists, not this personal corpus.
- Local model contract: `litellm/config.yaml` (Qwen Dell lanes + Ornith/Qwen Spark
  lanes via proxy).

## Decision Log

- Stage 0: treated the Claude `Scheduled/*/SKILL.md` files as the **prompt** side
  of the existing harness and the dated `*_report_*.md` / `*_log_*.md` files as
  the **emit** side, matching the files recently open in Cursor.
- Prefill L3/L4/L7/L9/L11 from those artifacts; skip re-asking what the reports
  already prove.
- L1 (2026-08-12): Vince chose durable new harness + local Qwen/Ornith; deferred
  retain/discard judgment to the agent. Recorded retain taxonomy/naming/corrections
  evidence; discard Cowork runtime and copy-duplication behavior. Mapped to
  rebuild-harness, not full SharePoint tree reset.
- L5 (2026-08-12): Wide auto required; Claude Code gated approach rejected.
  Safety = easy reverse + knowledge-graph provenance for agent "where did it go?"
  queries.
- L6 (2026-08-12): Success ranked provenance → inbox drain → near-zero drift.
  Delete policy left as assumption (byte-identical auto-delete only).
- L2 (2026-08-12): Operators = Vince + local-model agents. Jobs = daily digest
  (files + email), research-set historical cleanup, and ad-hoc world-class agent
  functions. Scope widened to email/meta-tags.
- L7 (2026-08-12): Exclude code/repos; email = Outlook + SharePoint attachments;
  VincePersonal only; beyond horizon → archive not churn.
- L8 (2026-08-12): Vince sole required approver and sole Stage 4 review authority.
- L10 Timing waived: no external deadline stated; research/plan can set phasing.
  Waived by Vince (implicit via sole ownership) / recorded by agent.
- L12 Taste waived: no subjective UI/brand calls beyond durable operator surface;
  research will propose conventions. Waived to avoid interview drift.
- Stage 2 convergence: all blocking lenses answered.
- Stage 3 (2026-08-12): Mode 
esearch+plan+execute (research then plan, then
  execute after separate authorization). Hard constraint: post-build runtime and
  maintenance agents use local models only — no paid token spend.
- Stage 4: freeze candidate for Vince sole approval; execution authorization
  remains outstanding after review approval.

## Handoff

- Target mode: research+plan+execute
- Candidate digest: (set after freeze)
- Spine skill: project-researcher, then project-orchestrator Stages 1-2 (spec
  gate), then Stage 3+ only after separate execution authorization
- Outstanding gates: Stage 4 review approval; project-orchestrator Stage 2 spec
  approval; execution authorization (not granted by discovery review)
