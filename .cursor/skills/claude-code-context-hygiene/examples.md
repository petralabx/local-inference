# Examples — Context Hygiene in Practice

Worked before/after scenarios for the workflows in [SKILL.md](SKILL.md). Each shows the
hygiene mistake, the orchestrated alternative, and the outcome.

## Example 1 — Long Autonomous Session

**Scenario:** An agent is autonomously implementing a multi-file feature over a long session.

**Before (context bloat):**
- Every "which file owns this?" question is asked inline, persisting into history.
- A full security pass is run in the main thread, dumping pages of scan output.
- No compaction until the model starts losing earlier requirements ("wait, what was the goal?").
- Result: huge token usage, degraded reasoning, a "forgot earlier context" error late in the run.

**After (orchestrated):**
1. `/context` at the start to baseline usage.
2. Quick checks go through `/btw` — zero history pollution.
3. The security pass is delegated to a subagent; only the findings return to the main thread.
4. `/compact` (general template) before each complex step, preserving file paths + test commands.
5. Periodic `/context` to confirm the thread stays lean.

**Outcome:** Main thread stays high-signal; tokens drop sharply; no lost-context errors.

## Example 2 — Feature Development

**Scenario:** Build an API endpoint, then its tests, then wire it into the UI.

**Before:**
- Tests are written inline amid dozens of red/green iterations, burying the implementation discussion.
- The thread carries all of that noise into the UI-wiring phase, which only needs the contract.

**After (orchestrated):**
1. Plan, then implement the endpoint.
2. `/btw` for quick questions during implementation.
3. Delegate test writing to the **test-writer** subagent (see
   [subagents/test-writer.md](subagents/test-writer.md)); it iterates in isolation and
   returns the finished tests.
4. `/compact` (phase-transition template): "Summarize previous phase outcomes. Focus on
   integration points and open tasks for the next phase."
5. Start UI wiring with a clean thread that holds only the contract and open tasks.

**Outcome:** Each phase starts focused; test iteration noise never reaches the UI phase;
higher-quality tests via the dedicated subagent.

## Example 3 — Debugging / Exploration

**Scenario:** Track down a flaky failure; several hypotheses turn out wrong.

**Before:**
- Every failed hypothesis stays in the thread.
- By the time the real root cause is found, the context is a graveyard of dead ends, and the
  successful fix is hard to distinguish from the noise.

**After (orchestrated):**
1. Use `/rewind` to abandon each wrong path as soon as it is disproven.
2. `/btw` for quick "is X even reachable?" checks.
3. Once stabilized on the fix, `/compact` (post-debugging template): "Retain only the final
   working approach, root cause, and successful tests. Remove all failed attempts."

**Outcome:** The thread ends with a clean record of root cause + working fix + passing tests;
fast recovery from dead-ends; minimal token waste.

## Quick before/after snippets

**Tangential question**
- Before: asks in the main thread -> permanent noise.
- After: `/btw is this the right config file?` -> answer, zero residue.

**Context getting heavy**
- Before: keep going until the model forgets the goal.
- After: `/context` -> `/compact Focus on goals + files changed; drop resolved debugging.`

**Deep specialized work**
- Before: run a sprawling code review inline.
- After: delegate to the code-reviewer subagent (`.claude/agents/code-reviewer.md`); bring back only the verdict.
