# Templates

Use these templates during a debugging session. Keep user-facing updates concise; keep evidence complete enough that another engineer can reproduce the reasoning.

## Intake

```text
Symptom:
Expected behavior:
Observed behavior:
Environment:
Failure category:
Domain tags:
Risk:
First reproduction target:
```

## Reproduction Evidence

```text
Command or flow:
Result:
Exit code or status:
Key output:
What this proves:
```

## Hypothesis Ledger

```text
Hypothesis 1:
Expected evidence if true:
Check:
Observed evidence:
Status:

Hypothesis 2:
Expected evidence if true:
Check:
Observed evidence:
Status:

Hypothesis 3:
Expected evidence if true:
Check:
Observed evidence:
Status:
```

## Minimal Fix Gate

```text
Root cause:
Minimal files:
Behavioral invariant:
Regression proof:
Verification gate:
Rollback:
```

## Browser Evidence

```text
Page:
Action:
Snapshot state:
Console evidence:
Network evidence:
Screenshot/profile evidence:
What this proves:
```

## DB or External Evidence

```text
System:
Staging guard run:
Read-only check:
Observed state:
Expected state:
What this proves:
```

## Blocker Report

```text
Current target:
Evidence gathered:
What failed:
Why blocked:
Likely next step:
Operator decision needed:
```

## Final RCA Report

```text
Symptom:
Root cause:
Evidence:
Fix:
Verification:
Residual risk:
Follow-up:
```

## Major Incident Artifact

For a critical or recurring incident, write a richer artifact in the repo's diagnostics or incident location when appropriate:

```markdown
# Root Cause Report: <title>

## Summary
<One paragraph>

## Impact
- Users affected:
- Systems affected:
- Duration:
- Severity:

## Timeline
- <time>: <event/evidence>

## Root Cause
<Specific broken transition or invariant>

## Contributing Factors
- <factor>

## Fix
- <change>

## Verification
- `<command>`: passed/failed, evidence

## Residual Risk
- <risk>

## Follow-Up
- <task>
```

## User-Facing Progress Update

```text
I reproduced the failure through <command/flow> and narrowed it to <domain/lifecycle step>. I’m checking <hypothesis> next, then I’ll make the smallest fix once the broken transition is confirmed.
```

## Completion Update

```text
Fixed. The issue was <root cause>. I verified it with <commands/browser checks>. Remaining risk: <risk or none>.
```
