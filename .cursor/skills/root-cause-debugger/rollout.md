# Rollout Guide

The canonical global skill is installed at:

```text
~/.cursor/skills/root-cause-debugger/
```

This repo-local copy exists so the skill can be reviewed, versioned, and shared with the VMC repo. Keep the global copy canonical for this machine and mirror material changes here when they should be shared.

Use it by naming the skill in a debugging request:

```text
/root-cause-debugger chat messages to the swarm never return successful completions
```

or:

```text
chat messages to the swarm never return successful completions, please fix it /root-cause-debugger
```

## What The Agent Should Do

For every real bug, the agent should:

1. Classify the symptom.
2. Reproduce with evidence.
3. Trace the relevant lifecycle.
4. Keep a hypothesis ledger.
5. State root cause and minimal fix scope before editing.
6. Apply the smallest safe fix.
7. Verify with narrow and wider gates.
8. Report root cause, evidence, verification, residual risk, and follow-up.

## Skill Composition

- `root-cause-debugger`: front-half diagnosis, lifecycle tracing, hypothesis control, minimal fix gate.
- `autonomous-verifier`: required when code changes are non-trivial, external systems are involved, or final proof needs a full matrix.
- `reliable-tdd-loop`: required when the fix needs a new contract invariant or failing-test-first discipline.
- `babysit`: use for PR comments, CI failures, and merge-readiness loops.
- Browser MCP: use for UI, stream, console, network, and visual evidence.
- VMC MCP: use for VMC context/progress/completion only after reading tool descriptors.

## VMC Invocation Examples

```text
/root-cause-debugger chat messages disappear after I send them
/root-cause-debugger todo dispatches never complete after the worker finishes
/root-cause-debugger trading v2 readiness is green when the paper ledger is stale
/root-cause-debugger swarm dispatch callback says success but the UI remains pending
/root-cause-debugger CI route contracts fail only on GitHub
```

## V1 Success Criteria

- The skill is globally discoverable and persisted.
- `SKILL.md` is concise and under 500 lines.
- Domain playbooks cover Chat, To-Dos, Trading, swarm dispatch, API, DB, CI, browser/UI, and flaky/race failures.
- Read-only helper scripts run successfully.
- The skill does not collide with `vmc-autopilot-oneshot` or autoresearch-only workflows.

## Stretch Improvements

Add these only after V1 proves useful:

- `known-failure-patterns.md` distilled from recurring `tasks/lessons.md` entries.
- A read-only command that maps a changed file to likely contract tests.
- A diagnostics artifact writer for major incidents under the active repo's `artifacts/diagnostics/`.
- Additional playbooks for Second-Brain, Projects, Email, Memory, MCP auth, and SharePoint.
