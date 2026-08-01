---
name: codebase-investigation
description: Investigate code by tracing data flow end-to-end, narrowing hypotheses with evidence, and reporting root cause with file:line proof. Use when debugging cross-cutting issues, answering "how does X work?", tracing a feature from entry point to data layer, or scoping the blast radius of a change across an unfamiliar repo.
---

# Codebase Investigation

A repeatable recipe for understanding unfamiliar code instead of ad-hoc searching.
Apply the universal lifecycle below in **any** repository. When working in the
agentic-swarm / VMC repo, also use the repo-specific commands in
[reference.md](reference.md).

## Universal Toolkit

| Tool | When to Use |
|------|-------------|
| Semantic search | Find code by meaning when you don't know the exact symbol/string |
| `rg` (ripgrep) | Exact search for symbols, strings, config values, imports |
| `git log -p --follow <file>` | Trace how a specific file evolved |
| `git log -S '<string>' --oneline` | Find the commit that introduced/removed a string ("pickaxe") |
| `git log -L :<fn>:<file>` | Trace the history of a single function |
| Language-native build/test | Confirm the repo is in a known-good state before/after |

Prefer the repo's own checks (typecheck, lint, unit slice) over guessing whether
something is broken.

## Investigation Lifecycle

### 1. Orient — Scope the Question
- State the observable symptom or the precise question in one sentence.
- Decide: runtime issue (logs, errors, a failing request) or structural question
  (architecture, data flow, ownership)?
- Identify the likely entry point (route, CLI command, event handler, cron, UI
  action). Start there, not in the middle.

### 2. Trace — Follow the Data Flow
Work top-down from the entry point toward the data/IO layer:
1. **Entry point** — find the handler (`rg` the route path, command name, or event).
2. **Call chain** — read the handler, list the functions/services it calls, follow
   each import to its definition (respect barrels/index files; don't bypass them).
3. **Data/IO edge** — stop at the DB query, file write, or external call. The bug
   or behavior almost always lives at an edge or a transform just before it.

Use context flags for precision:
```bash
rg -C 5 "functionName" src/          # 5 lines of surrounding context
rg -t ts "class MyClass" src/        # filter by language
rg -l "pattern" src/                 # just the file paths that match
```

### 3. Narrow — Eliminate Hypotheses
For each hypothesis, demand concrete evidence — a code path, a log line, a test.
- If two focused searches produce no evidence, discard the hypothesis.
- Do not guess. Track what you checked and what you could not confirm.

### 4. Verify — Confirm the Finding
- Run the repo's fast check (typecheck / unit slice / smoke) to confirm a
  known-good baseline.
- If proposing a fix, re-run the relevant tests and show they pass.

### 5. Report — Document What You Found
Structure findings as:
- **Symptom** — what was observed.
- **Root cause** — the specific code path or config, cited as `file:line`.
- **Evidence** — paths, line numbers, command output.
- **Recommendation** — fix, further investigation, or "no action needed".

## When to Stop
- After 3 rounds of search with no new evidence, report what you know and the open
  questions — don't spiral.
- If the answer requires runtime data you can't access (prod logs, a live session),
  say so explicitly.
- If the blast radius is large or crosses several critical areas, surface that and
  get alignment before proposing sweeping changes.

## Repo-specific playbook
For agentic-swarm / VMC investigations — module ownership, blast-radius mapping,
barrel/shim rules, agent/swarm tracing, and the exact verification commands — see
[reference.md](reference.md).
