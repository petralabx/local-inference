---
project: sharepoint-doc-org-cutover
created: 2026-08-15T18:48:00Z
status: executing
approved_by: Vince (cos@petrasoap.com)
approved_at: 2026-08-15T18:46:00Z
model_plan:
  planner: frontier-orchestrator
  builder: frontier-builder
  mechanical: frontier-fast
  critic: frontier-critic
budget:
  max_parallel_phases: 2
  max_attempts_per_phase: 3
  time_budget_min: 0
  commit_push_each_phase: true
---

# VincePersonal cutover (locked tree)

## Mission

Align the already-merged harness (PR #25) to the 2026-08-15 locked tree, then
cut over VincePersonal: one Save Path, one Organizer, Spark classify, full
unique-file drain, mail in the same era, and a proven cadence. Do not rebuild
P1–P8.

## Success Criteria

- [ ] Config pins classify to Dell LiteLLM `local-driver` with `local-coder`
      fallback; tests fail on paid cloud bases
- [ ] Known-folder capture paths exist: `00_Inbox/_from_desktop|_from_documents|_from_downloads`
- [ ] Filenames stay human-readable; date/type/version live in the journal
- [ ] Petra map (ADR 0016) and unique-hash skip (ADR 0017) have fixture tests
- [ ] No inbox ceiling and no auto-archive in v1 config
- [ ] Five-file smoke on VTA journals moves and `harness reverse` undoes them
- [ ] Redirect script applies the same method on VTA; taylorvalton is documented
      as blocked until Vince is at that machine
- [ ] Daily Task Scheduler job exists; after proof it runs 06:00/10:00/14:00/18:00
      America/Toronto
- [ ] Mail first pass is last 90 days; remainder is a later drain step, not a
      new Outlook taxonomy

## Scope

- In:
  - Harness config, classify, inbox, digest, mail window, drain map, tests
  - ADRs and `docs/locked-tree.md` already written under the harness tree
  - Redirect script + scheduler job definition
  - Live VTA smoke and VTA redirect only when an execute session is started
- Non-goals:
  - Rebuilding the P1–P8 harness
  - Filing code trees or secrets
  - Paid cloud tokens
  - New COS / Ask app
  - taylorvalton redirect while Vince is away
  - Hiding Petra folders that are not empty
  - Auto-archive or inbox alerts

## Phases

### P1 — Align harness to locked tree
- deliverables: Spark classify aliases; capture-folder config; readable-name
  path (no coded prefix law); no ceiling; no auto-archive; tests
- depends_on: []
- owns: [".orchestrator/sharepoint-doc-org-harness/config/**", ".orchestrator/sharepoint-doc-org-harness/harness/config.py", ".orchestrator/sharepoint-doc-org-harness/harness/classify/**", ".orchestrator/sharepoint-doc-org-harness/harness/jobs/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_cutover_p1_*.py", ".orchestrator/sharepoint-doc-org-cutover/**"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_cutover_p1_`
- role: builder
- competitive: false

### P2 — Drain map and unique-hash skip
- deliverables: Petra→VincePersonal map config; unique-file classify; hash
  skip for byte-identical copies; fixture tests
- depends_on: [P1]
- owns: [".orchestrator/sharepoint-doc-org-harness/config/**", ".orchestrator/sharepoint-doc-org-harness/harness/actions/**", ".orchestrator/sharepoint-doc-org-harness/harness/jobs/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_cutover_p2_*.py"]
- forbidden: ["litellm/**", "scripts/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_cutover_p2_`
- role: builder
- competitive: false

### P3 — One redirect method (script)
- deliverables: Windows known-folder redirect script targeting the three
  `00_Inbox/_from_*` folders; dry-run flag; docs for VTA apply and
  taylorvalton wait
- depends_on: [P1]
- owns: [".orchestrator/sharepoint-doc-org-harness/scripts/**", ".orchestrator/sharepoint-doc-org-harness/docs/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_cutover_p3_*.py"]
- forbidden: ["litellm/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_cutover_p3_`
- role: builder
- competitive: false

### P4 — Mail window and cadence job
- deliverables: 90-day then remainder mail config; Task Scheduler definition
  (daily, then 06/10/14/18 America/Toronto); tests; no live mailbox required
- depends_on: [P1]
- owns: [".orchestrator/sharepoint-doc-org-harness/harness/mail/**", ".orchestrator/sharepoint-doc-org-harness/harness/jobs/**", ".orchestrator/sharepoint-doc-org-harness/scripts/**", ".orchestrator/sharepoint-doc-org-harness/docs/**", ".orchestrator/sharepoint-doc-org-harness/tests/test_cutover_p4_*.py"]
- forbidden: ["litellm/**", ".github/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_cutover_p4_`
- role: builder
- competitive: false

### P5 — Fixture harden
- deliverables: full cutover pytest slice green; operator execute checklist
  that names VTA smoke, VTA redirect, drain, mail, taylorvalton, Petra hide
- depends_on: [P2, P3, P4]
- owns: [".orchestrator/sharepoint-doc-org-harness/tests/test_cutover_p5_*.py", ".orchestrator/sharepoint-doc-org-harness/docs/**", ".orchestrator/sharepoint-doc-org-cutover/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `cd .orchestrator/sharepoint-doc-org-harness && python -m pytest -q -k test_cutover_`
- role: builder
- competitive: false

## Risks & Rollback

- Live drain while Vince is away → this SPEC’s automated phases are code and
  fixtures only. Live smoke/redirect/drain is a later execute session.
- Broken Desktop redirect → script must support `--dry-run` and `--undo`
  (restore previous known-folder targets).
- Spark proxy down → digest fails closed; no paid fallback (ADR 0014).
- Dual machine habit → do not save on taylorvalton until the same redirect
  is applied (ADR 0022).
- Accidental delete → `delete_duplicates` stays false; `harness reverse` is
  the rollback for journaled moves.

## Worktree Plan

- base branch: `proj/sharepoint-doc-org-cutover`
- phase branches: `proj/sharepoint-doc-org-cutover/phase-<k>-<name>`
- integration branch: `proj/sharepoint-doc-org-cutover/integration`
- delivery: one integration PR after P5; live cutover is not part of that PR

## Approved decisions (2026-08-15)

Vince confirmed “this is the plan.” Canonical summary:
`.orchestrator/sharepoint-doc-org-harness/docs/locked-tree.md`.
Code-phase `model_plan` stays frontier. Steady-state Organizer tokens use
Spark aliases through Dell LiteLLM (ADR 0014).

Delivery PR: https://github.com/petralabx/local-inference/pull/26
MC-Checkout: dsp_msvl6idyawe4jt

