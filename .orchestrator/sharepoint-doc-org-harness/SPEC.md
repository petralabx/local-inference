---
project: sharepoint-doc-org-harness
created: 2026-08-12T11:15:00Z
status: approved
approved_by: Vince (cos@petrasoap.com)
approved_at: 2026-08-12T11:15:00Z
model_plan:
  planner: frontier-orchestrator
  builder: frontier-builder
  mechanical: frontier-fast
  critic: frontier-critic
budget:
  max_parallel_phases: 2
  max_attempts_per_phase: 3
  time_budget_min: 0
  soft_pause_usd: 100
  on_soft_pause: report-estimate-and-wait
  commit_push_each_phase: true
---

# SharePoint Document Organization Harness

## Mission

Build a durable, testable Python harness that organizes Vince’s files and Outlook
mail on VincePersonal SharePoint with wide-auto daily digest, 12-month historical
cleanup then archive-in-place, content-hash identity, Docling + local-LLM
classification, move-not-copy filing, SQLite reverse journal, and a queryable
provenance graph — so agents can answer where a file went after rename/move,
without Claude Cowork and without paid cloud LLM tokens in steady state.

## Success Criteria

- [ ] Provenance: CLI/API resolves former path or filename to current location for
      10 synthetic fixture moves without reading raw logs by hand
- [ ] Reverse: `harness reverse --run-id <id>` undoes a fixture run’s mutations
      (journal-driven) and exits 0
- [ ] Inbox sorter: fixture inbox files are **moved** (not copied); second run is
      idempotent (no new `_vNN` duplicates for same content-hash)
- [ ] Dedup: fclones wrap reports byte-identical groups; auto-delete path only for
      graph-confirmed duplicates with tombstone (or dry-run when delete disabled)
- [ ] Extract/classify: Docling (+ OCRmyPDF for scan PDF fixtures) feeds local
      LiteLLM classify; output names match `YYYY-MM-DD_PREFIX_Description_vNN.ext`
- [ ] Mail: Graph-backed fixture (or recorded cassette) files attachment into
      SharePoint inbox/target and can ensure an Outlook folder/rule idempotently
- [ ] Daily digest job entrypoint runs end-to-end on fixtures and writes a health
      markdown report with inbox count + duplicate + compliance metrics
- [ ] Steady-state config pins inference base URL to Dell LiteLLM proxy; tests fail
      if a paid cloud OpenAI/Anthropic base URL is configured for classify
- [ ] Code/repo exclude globs skip `node_modules`, `.git`, and `agentic-swarm`
      trees in scans
- [ ] Operator docs describe VTA single-writer schedule + laptop ad-hoc provenance

## Scope

- In:
  - New harness package under `.orchestrator/sharepoint-doc-org-harness/harness/`
  - Tests under `.orchestrator/sharepoint-doc-org-harness/tests/`
  - Config, journals, fixtures, operator docs under the same slug tree
  - VincePersonal SharePoint file ops (sync-root and/or Graph)
  - Outlook folder/rules + attachment filing (delegated Graph)
  - Local LiteLLM classify (`local-fast` / `local-primary`)
  - SQLite reverse journal + provenance projection (NetworkX phase-0; Neo4j
    optional adapter behind interface)
  - fclones / Docling / OCRmyPDF wraps
  - Seed import from existing `correction_rules.json` + taxonomy prefixes
- Non-goals:
  - Product code in `litellm/`, `scripts/` (local-inference roots), or team SP sites
  - Paperless-ngx / TagSpaces / Karakeep as runtime SoT
  - Paid cloud LLM tokens for classify/digest/provenance
  - Active churn of files older than 12 months (archive-in-place only)
  - Filing automation inside git repos / `node_modules`
  - Replacing OneDrive sync client (may use it; SoT remains SharePoint library)

## Phases

### P1 — Scaffold and contracts
- deliverables: Python package layout, `pyproject.toml`, config schema (paths,
  LiteLLM base URL, exclude globs, 12-month horizon, inbox ceiling 100),
  taxonomy prefix table, correction-rules loader, README stub; `pytest` collects
- depends_on: []
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p1_*.py", ".orchestrator/sharepoint-doc-org-harness/pyproject.toml", ".orchestrator/sharepoint-doc-org-harness/README.md", ".orchestrator/sharepoint-doc-org-harness/config/**"]
- forbidden: ["litellm/**", "scripts/**", ".github/**", "docs/runbooks/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p1_`
- role: builder
- competitive: false

### P2 — Identity, journal, reverse
- deliverables: content-hash identity; append-only SQLite action journal; CLI
  `harness reverse --run-id`; unit tests proving undo of fixture rename/move
- depends_on: [P1]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/identity/**", ".orchestrator/sharepoint-doc-org-harness/harness/journal/**", ".orchestrator/sharepoint-doc-org-harness/harness/cli/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p2_*.py"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p2_`
- role: builder
- competitive: false

### P3 — Provenance graph projection
- deliverables: journal→graph projector; query API/CLI
  `harness where --path|--name|--hash`; NetworkX backend default; Neo4j adapter
  interface stubbed; fixture provenance tests
- depends_on: [P2]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/provenance/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p3_*.py"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p3_`
- role: builder
- competitive: false

### P4 — Extract and classify
- deliverables: Docling wrap, OCRmyPDF scan lane, LiteLLM classify client pinned
  to local proxy, naming convention builder, correction-rules-first routing;
  offline cassette/fixture tests (no live GPU required for CI)
- depends_on: [P1]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/extract/**", ".orchestrator/sharepoint-doc-org-harness/harness/classify/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p4_*.py", ".orchestrator/sharepoint-doc-org-harness/tests/fixtures/extract/**"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p4_`
- role: builder
- competitive: false

### P5 — File actions (inbox, archive, dedupe)
- deliverables: move-not-copy inbox sorter with processed manifest; 12-month
  archive-in-place lane; fclones wrap + duplicate plan apply (delete gated by
  config flag defaulting to tombstone/soft-delete); scope excludes
- depends_on: [P2, P4]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/actions/**", ".orchestrator/sharepoint-doc-org-harness/harness/dedupe/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p5_*.py", ".orchestrator/sharepoint-doc-org-harness/tests/fixtures/inbox/**"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p5_`
- role: builder
- competitive: false

### P6 — Outlook and attachments
- deliverables: delegated Graph mail client; idempotent folder ensure; attachment
  save into SharePoint inbox/target; rule ensure helper; tests via recorded
  Graph cassettes or fakes (no live mailbox required for acceptance)
- depends_on: [P2, P4]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/mail/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p6_*.py", ".orchestrator/sharepoint-doc-org-harness/tests/fixtures/mail/**"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p6_`
- role: builder
- competitive: false

### P7 — Daily digest job and operator surface
- deliverables: `harness digest` orchestrating scan→classify→act→report;
  health report writer; Task Scheduler / Windows job install notes; VTA
  single-writer + laptop query docs; paid-URL guard test
- depends_on: [P3, P5, P6]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/jobs/**", ".orchestrator/sharepoint-doc-org-harness/docs/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_p7_*.py"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_p7_`
- role: builder
- competitive: false

### P8 — Integration harden and publish prep
- deliverables: end-to-end fixture pipeline test; OSS adopt/wrap table mirrored
  in docs; packaging notes for promotion to `petralabx/sharepoint-doc-org-harness`;
  smoke checklist for live VTA cutover (manual)
- depends_on: [P7]
- owns: [".orchestrator/sharepoint-doc-org-harness/tests/test_p8_*.py", ".orchestrator/sharepoint-doc-org-harness/docs/**", ".orchestrator/sharepoint-doc-org-harness/README.md"]
- forbidden: ["litellm/**", "scripts/**", ".github/workflows/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest tests/ -q`
- role: builder
- competitive: false

## Risks & Rollback

- Wide auto on large corpus → start with fixture + dry-run flags; journal every
  mutation; `harness reverse --run-id` is primary rollback
- Graph delegated auth blocked → fall back to sync-root FS for files; mail phase
  may hard-stop with BLOCKER if tenant policy forbids Mail.ReadWrite
- LiteLLM/proxy down → digest fails closed (no cloud fallback); retry next run
- Dual-writer VTA+laptop → document single-writer lock file on VTA; laptop
  query-only against journal/graph
- Docling/OCR heavy CPU → batch limits + backlog queue; priority ≤12-month inbox
- Accidental delete → default `delete_duplicates: false`; only tombstone until
  Vince enables delete; reverse restores from journal sidecar copies when configured
- Publishing new GitHub repo → P8 prep only; creating `petralabx/...` is operator
  step outside automated phase merge

## Worktree Plan

- base branch: `proj/sharepoint-doc-org-harness`
- phase branches: `proj/sharepoint-doc-org-harness/phase-<k>-<name>`
- integration branch: `proj/sharepoint-doc-org-harness/integration`
- delivery: one integration PR (or promotion PR into new harness repo) after
  hardener; **no phase execution until this SPEC is approved and Vince separately
  confirms execution start** if required by session policy

## Approved decisions (2026-08-12)

1. **Graph mutate priority:** Graph drive item IDs when online; sync-root for
   hash/dedupe scans.
2. **KG backend phase-0:** NetworkX + SQLite journal first; Neo4j optional later
   (no Docker day one).
3. **Duplicate deletes:** default **off** (tombstone only) until Vince enables.
4. **Inbox ceiling:** ≤100 active items.
5. **model_plan:** frontier role placeholders accepted for build-time agents.
   Steady-state classify/digest remains local LiteLLM only (not a model_plan item).
