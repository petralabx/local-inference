---
name: uat-runner
description: Run PLX portal User Acceptance Testing (UAT) scenarios and record results as governed evidence. Use when asked to run UAT, execute acceptance tests for the customer portal, validate go-live readiness, or update the portal UAT quality-ledger. Checks out the MC task via the PLX-MC MCP, runs the UAT cases, and writes results to the portal uat quality-ledger so Mission Control sees the same posture under BKT-UAT.
---

# UAT Runner Skill

Run User Acceptance Testing for the PLX customer portal and land the results in the
**one** system of record so humans (in Mission Control) and agents see the same UAT
posture. This skill is the `agentic-swarm` half of the cross-repo UAT parity contract
(`PLX_MC/docs/modules/uat/README.md`).

## Invariant

UAT results have a single source of truth: the **portal** `uat` quality-ledger
(`plx-customer-portal/docs/portal/quality-ledger/uat.artifacts.json`, schema
`vmc-quality-ledger/v1`) and its SharePoint UAT Feedback list. This skill *runs* UAT
and *writes evidence*; it never creates a second source of truth. Mission Control is a
read-only lens (Loop Ledgers → `BKT-UAT`).

## Workflow

1. **Govern the run (PLX-MC MCP).** Use the `PLX-MC` MCP server (registered in
   `.cursor/mcp.json`; needs `MC_MCP_API_KEY` + `MC_OPERATOR_EMAIL` in env):
   - `mc_self_check` → confirm auth + connectivity.
   - `mc_search_tasks` for the UAT task under `BKT-UAT` (e.g. "Parallel system
     testing"), or `mc_create_task` in `BKT-UAT` if none exists.
   - `mc_checkout_task` → keep the `MC-Checkout: dsp_…` stamp for the PR body.
2. **Run the UAT cases.** Execute the portal UAT scenarios (SOP:
   `plx-customer-portal/docs/UAT-SOP-Customer-Portal.md`; seed test data via
   `portal/scripts/create-uat-test-customers.ts`). Capture pass/fail + evidence per
   case.
3. **Record to the portal ledger.** Update
   `docs/portal/quality-ledger/uat.artifacts.json` — one artifact per UAT area/case
   (`artifact_type: "test_gap" | "ticket"`, real `status`/`severity`/`safety_class`,
   non-empty `evidence`). Regenerate the `.md` mirror via the portal's ledger script.
   Use the canonical shape in `PLX_MC/docs/templates/quality-ledger/`.
4. **Close the loop.** `mc_report_progress` / `mc_complete_task` with the evidence
   summary (+ `rollback`), then open the portal PR carrying the `MC-Checkout` stamp.

## Guardrails

- Do **not** write UAT results into PLX_MC — it pulls them from the portal ledger.
- Do **not** fabricate UAT pass results; a case with no evidence is `missing_test`,
  not `verified` (the ledger validator rejects `verified` with empty evidence).
- Portal changes target the portal repo's working branch and need the normal portal
  review; this skill prepares them, it does not bypass portal governance.

## Reuse

- `vmc-sync` — the general MC checkout/progress/complete pattern this builds on.
- `PLX_MC/docs/modules/uat/README.md` — the cross-repo UAT parity contract.
- `PLX_MC/docs/templates/quality-ledger/` — the `vmc-quality-ledger/v1` template.
