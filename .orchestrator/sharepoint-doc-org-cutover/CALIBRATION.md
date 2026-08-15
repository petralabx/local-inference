# Calibration Brief

Restated task:
Align the existing VincePersonal harness to the locked tree, then run live cutover (smoke, one redirect method, full drain, mail, cadence) without rebuilding P1–P8.

Context to use:
- `docs/locked-tree.md` and ADRs 0001–0023 under `.orchestrator/sharepoint-doc-org-harness/`
- Merged harness at `9dbf0c1` (PR #25)
- LiteLLM Spark aliases in `C:\Users\vince\local-inference\litellm\config.yaml`

Assumptions:
- Vince is absent for live Desktop redirect on taylorvalton and for Judgement on journal-vs-Brain diffs
- Graph mail auth already works on VTA or the mail phases hard-stop with BLOCKER
- `petralabx/local-inference` is the delivery repo until a standalone harness repo exists

Non-goals:
- Rebuilding the P1–P8 harness
- Filing git / `node_modules` / `.venv` / `agentic-swarm` trees
- Putting secrets in VincePersonal
- Paid cloud classify
- Auto-archive or inbox ceiling
- A new COS app
- Hiding Petra folders before they are empty

Success criteria:
- Harness config and tests match the locked tree (Spark classify, capture folders, readable names, map, no ceiling)
- Five-file smoke journals moves and reverses
- One redirect method exists as an installable script; VTA can apply it; taylorvalton waits until Vince is at that machine
- Unique-file drain + hash skip is testable on fixtures before live
- Mail 90-day window is configured; live mailbox is a later operator phase
- Cadence job exists: daily until proven, then 06/10/14/18 America/Toronto

Plan implications:
- Code phases can run without Vince
- Live file moves, VTA known-folder apply, Petra folder hide, and taylorvalton apply need Vince or a later session
- Do not start the live drain in the same commit that only saves the contract

Remaining questions:
No blockers to planning. Live cutover waits for Vince or an explicit later execute session.
