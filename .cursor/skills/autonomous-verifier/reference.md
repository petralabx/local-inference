# Autonomous Verifier Reference

## Standard Verification Command Matrix

Run relevant commands from the package that owns the touched behavior.

For VMC web work, run from `apps/vmc-web`:

```bash
# Static quality
npm run lint
npm run typecheck

# Reliability and behavior
npm test
npm run test:contracts
npm run test:e2e:smoke
```

The reusable wrapper `.cursor/skills/autonomous-verifier/scripts/validate.sh` runs the VMC package checks from `apps/vmc-web` and fails closed if the expected package or contract script is missing.

For Python reliability workers:

```bash
pytest -q src/api
python -m pytest -q src/pipelines
```

For staging DB or external API checks:

```bash
source ~/.secrets-env.staging
bash scripts/assert-staging-context.sh
```

## Reliability Metrics Checklist

Track at minimum:

- `callbackSuccessRate`
- `staleTodoCountOver24h`
- `reconcileLagMs`
- `dispatchPollTakeoverCount`
- `chatFailureVisibilitySlaMs`

Include baseline and post-change values in the report.

## Browser Validation Checklist

1. `browser_tabs` with action `list`
2. `browser_snapshot` before interaction
3. Interaction by ref (`browser_click`, `browser_fill`, `browser_type`)
4. `browser_snapshot` again after structural changes
5. Verify expected text/state with snapshot evidence
6. If blocked after four attempts, stop and record blocker

## VMC MCP Execution Order

1. `vmc_get_context`
2. `vmc_checkout_task`
3. Implementation and verification
4. `vmc_report_progress` at milestones
5. `vmc_get_repo_health`
6. `vmc_get_dependency_risks`
7. `vmc_complete_task`

## Artifact Template

Use this report shape in phase artifacts:

```markdown
# REPORT

## Scope
- Files touched
- Reason for each change

## Verification
- Commands run
- Exit codes
- Contract and integration outcomes

## Reliability Metrics
- Baseline values
- Post-change values
- Delta and interpretation

## Browser and External Validation
- Snapshot evidence summary
- API and DB evidence summary

## Risks and Rollback
- Residual risks
- Rollback steps
```

## Recurrence Prevention

When a repeated failure pattern appears:

1. Append pattern and fix to `tasks/lessons.md`.
2. Refine an existing `.cursor/rules/*.mdc` rule that prevents recurrence, unless a new rule is explicitly approved.
3. Add a targeted verification check to `.cursor/skills/autonomous-verifier/scripts/validate.sh`.

## AutoPilot Hybrid Evidence Bridge

When invoked from `vmc-autopilot-oneshot` Hybrid mode, write verifier results into the active evidence bundle instead of inventing a second artifact shape:

- command outcomes go in `commands.log`
- MCP calls go in `mcp-evidence.json`
- numeric pass/fail and freshness data go in `metrics.json`
- human interpretation goes in `REPORT.md`
- residual risks and rollback notes go in `risks.md`

The phase-exit gate name is `run_phase_exit_gate(context)` and its detector contracts live in [`../vmc-autopilot-oneshot/reference.md`](../vmc-autopilot-oneshot/reference.md).
