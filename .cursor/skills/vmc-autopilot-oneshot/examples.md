# VMC AutoPilot OneShot Examples

## Legacy Waterfall Trigger

```text
VMC AutoPilot PA :: callback preflight and baseline metrics
```

Legacy triggers intentionally stay on the waterfall contract during hybrid canary.

## Explicit Legacy Trigger

```text
Run VMC AutoPilot Phase B: dispatch contract parity across todo/chat/cron.
```

## Fully Parameterized Legacy Trigger

```text
Run VMC_WATERFALL_AUTOPILOT for phase=C goal="harden reconciliation and chat failure visibility" branch="feat/vmc-reliability/phase-c-reconcile-chat-failure".
```

## Hybrid Canary Trigger

```text
VMC AutoPilot Hybrid PA :: callback preflight and baseline metrics
```

## Fully Parameterized Hybrid Trigger

```text
Run VMC_HYBRID_AUTOPILOT for phase=C goal="harden reconciliation and chat failure visibility" branch="feat/vmc-reliability/phase-c-reconcile-chat-failure".
```

## Legacy Alias Pack

```text
VMC AutoPilot PA :: callback preflight + baseline
VMC AutoPilot PB :: dispatch parity + callback_url guarantees
VMC AutoPilot PC :: reconciliation + chat failure surfacing
VMC AutoPilot PD :: today/system pulse reliability parity
VMC AutoPilot PE :: self-healing and autoresearch loops
```

## Hybrid Alias Pack

```text
VMC AutoPilot Hybrid PA :: callback preflight + baseline
VMC AutoPilot Hybrid PB :: dispatch parity + callback_url guarantees
VMC AutoPilot Hybrid PC :: reconciliation + chat failure surfacing
VMC AutoPilot Hybrid PD :: today/system pulse reliability parity
VMC AutoPilot Hybrid PE :: self-healing and autoresearch loops
```

## Hybrid Operator Checklist

```text
Hybrid AutoPilot Progress - phase=<A-E> branch=<branch>
- [ ] 1) Read .cursor/plans/ledger/<branch>/ledger.jsonl before edits
- [ ] 2) If ledger is absent/inconsistent, halt in rehydration mode
- [ ] 3) Declare ownership globs and evidence bundle path
- [ ] 4) Write gate_entry and plan records with plan_hash
- [ ] 5) Execute scoped work with heartbeat every 10 minutes or VMC checkpoint
- [ ] 6) Run autonomous verifier and any TDD/browser/MCP checks
- [ ] 7) Run all detector functions from reference.md
- [ ] 8) Write REPORT.md, artifacts.json, commands.log, mcp-evidence.json, metrics.json, ledger-snapshot.jsonl, risks.md
- [ ] 9) Run scripts/validate-evidence-bundle.py, scripts/validate-ledger.py, and scripts/validate-detectors.py
- [ ] 10) Append gate_exit only after all hard metrics pass
- [ ] 11) Run babysit loop until CI/comments are green
```

## Session Resume Checklist

Use this before edits in a resumed hybrid session:

```text
Resume Hybrid AutoPilot
1. Open .cursor/plans/ledger/<branch>/ledger.jsonl.
2. Locate the latest gate_entry for the active phase.
3. Locate the latest gate_exit for the active phase.
4. Confirm the active plan_hash and evidence_ref.
5. Re-read metrics.json from evidence_ref.
6. If any record is missing or contradictory, enter rehydration mode and halt.
```

## Rollback Checklist

```text
Rollback Hybrid AutoPilot
1. Stop invoking Hybrid aliases.
2. Use legacy `VMC AutoPilot P{A-E}` or `VMC_WATERFALL_AUTOPILOT`.
3. Confirm emitted prompt says `Run VMC_WATERFALL_AUTOPILOT`.
4. Do not delete existing hybrid artifacts; keep them as canary evidence.
```

## Evidence Bundle Skeleton

```text
artifacts/autopilot/2026-04-24-a-callback-preflight/
|-- REPORT.md
|-- artifacts.json
|-- commands.log
|-- mcp-evidence.json
|-- ledger-snapshot.jsonl
|-- metrics.json
`-- risks.md
```
