# Autonomous Verifier Examples

## Example 1: Contract-First Bug Fix

Scenario: stale todos remain in `progress` after callback failure.

1. Add failing contract test in reliability contracts suite.
2. Implement scoped reconciliation fix.
3. Re-run contract, integration, and typecheck.
4. Capture before/after stale-count metric.
5. Document evidence in phase `REPORT.md`.

## Example 2: Browser Snapshot Validation

Use this sequence for UI verification:

1. `browser_tabs` with action `list`
2. `browser_snapshot` to collect current refs
3. `browser_click` target ref
4. `browser_snapshot` again
5. Assert expected UI state from updated snapshot

Never click by guess; always use refs from the latest snapshot.

## Example 3: VMC Progress Reporting

Use progress reporting around milestones:

```text
vmc_get_context(depth=full)
vmc_checkout_task(todoId="phase-b-dispatch-parity")
vmc_report_progress(todoId="phase-b-dispatch-parity", progressPct=40, notes="Added shared dispatch metadata builder and tests")
vmc_report_progress(todoId="phase-b-dispatch-parity", progressPct=80, notes="Contract tests passing in staging")
vmc_complete_task(todoId="phase-b-dispatch-parity", evidence="All checks green, report generated, PR merge-ready")
```

## Example 4: Staging Preflight for DB Validation

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
psql "$DATABASE_URL" -c "select now();"
```

Stop if staging guard fails.

## Example 5: Correction Loop with Babysit

1. Collect all comments and CI failures.
2. Fix only validated issues with minimal diff.
3. Re-run failed checks.
4. Re-open comments and CI; repeat until green.
5. Add lessons entry for any non-obvious failure cause.
