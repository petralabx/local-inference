# Reference — Context Hygiene & Command Orchestration

Deep reference for [SKILL.md](SKILL.md). Read this when you need command semantics,
the full compaction template library, or cross-version / cross-tool notes.

## 1. Command Deep Dive

What each command does to context, and the gotchas that matter for hygiene.

### `/btw`
- **Effect:** Ask a question or leave a note that has full access to current context but
  does **not** persist into the conversation history. No tools run.
- **Use for:** quick clarifications, reminders, "is this the right file?", sanity checks.
- **Gotcha:** it is for *thought*, not *action*. The moment you need a tool, a file edit,
  or a follow-up turn, it is the wrong command — escalate to `/fork` or a subagent.
- **Availability fallback:** if `/btw` is not in `/help`, emulate zero-pollution by writing
  the briefest inline note and removing it, or keep a scratchpad file you delete after.

### `/compact <instructions>`
- **Effect:** Summarizes the conversation so far into a compact form, controlled by your
  instructions, then continues with the summary in place of the raw history.
- **Use for:** reclaiming context before complex steps and at phase boundaries.
- **Gotcha:** never run it bare. Without instructions you lose control over what is kept
  vs. dropped. Always precede with `/context` and name what to preserve and what to drop.
- **Prevention > cure:** compact *before* degradation, not after. A proactive compact with
  strong instructions beats an emergency compact of an already-noisy thread.

### `/fork`
- **Effect:** Branches the session so side work runs in isolation from the main thread.
- **Use for:** tangents that need tools or multiple turns but should not live in the main history.
- **Gotcha:** forking core work fragments your mental model — only isolate genuinely
  tangential work. If `/fork` is unavailable, a subagent achieves the same isolation.

### `/agents` + subagents
- **Effect:** Manage specialized subagents that each run in their own isolated context with
  a custom prompt and tool set.
- **Use for:** deep, focused, reusable work (test writing, security review, code review,
  research) that would otherwise flood the main thread with intermediate noise.
- **Gotcha:** give the subagent a crisp scope and return only the result. A subagent with a
  vague brief just relocates the mess.

### `/context`
- **Effect:** Shows token usage and what is consuming the context window.
- **Use for:** a health check before compacting/clearing and periodically in long sessions.
- **Gotcha:** it is diagnostic only — pair it with an action (`/compact`, subagent, `/clear`).

### `/rewind`
- **Effect:** Restores the session to a previous checkpoint, discarding the steps after it.
- **Use for:** abandoning a wrong path during debugging/exploration.
- **Gotcha:** rewinding discards work after the checkpoint — capture anything still useful
  (a root cause, a working snippet) before you roll back.

### `/clear`
- **Effect:** Wipes the conversation context for a fresh start.
- **Use for:** a completely unrelated new phase.
- **Gotcha:** everything is lost. Before clearing, record keepers: decisions, modified file
  paths, and the exact test/verify commands.

## 2. Compaction Template Library

Pick the closest template and fill the angle-bracket slots. Always pair with `/context` first.

**General**
```text
/compact Focus on architecture decisions, key requirements, current goals, and all
modified file paths. Preserve test commands/results. Drop repetitive debugging and dead-ends.
```

**Phase transition**
```text
/compact Summarize previous phase outcomes. Focus on integration points and open tasks
for the next phase.
```

**Post-debugging**
```text
/compact Retain only the final working approach, root cause, and successful tests.
Remove all failed attempts.
```

**Refactor**
```text
/compact Preserve the target architecture, the list of files changed, and remaining
call sites to update. Keep typecheck/test commands. Drop intermediate edit chatter and
reverted attempts.
```

**Research / exploration**
```text
/compact Keep the question, the sources/finds that mattered, and the recommendation with
its rationale. Drop discarded leads and raw dumps.
```

**Integration / cross-module**
```text
/compact Keep the contract between modules (inputs, outputs, invariants), the integration
points touched, and the open wiring tasks. Preserve the end-to-end test command. Drop
single-module debugging detail already resolved.
```

**Pre-handoff (to a human or another agent)**
```text
/compact Produce a clean handoff: current goal, what is done, what remains, files changed,
how to verify (exact commands), and known risks. Drop everything not needed to resume.
```

### Writing your own
1. **Focus on:** goals + invariants that must survive.
2. **Preserve:** files changed, exact test/verify commands + results, key decisions, open tasks.
3. **Drop:** failed attempts, repetitive debugging, resolved tangents, raw output dumps.

## 3. Command Availability & Compatibility

Command names and behavior vary across Claude Code versions and across tools. Before
relying on a command in an unfamiliar environment:

- Run `/help` to confirm the command exists and check its exact syntax.
- If a command is missing, use the documented fallback:
  - `/btw` -> briefest inline note or a scratchpad file you delete afterward.
  - `/fork` -> a subagent via `/agents` for the same isolation.
  - `/rewind` -> manual checkpointing (note a known-good state you can reconstruct).
- Treat the decision framework — not any single command — as the durable part of this
  skill. The questions ("needs tools/multi-turn?", "will it pollute the thread?") hold even
  when the command surface changes.

### Cross-tool mapping (approximate)

| Intent | Claude Code | General equivalent |
|---|---|---|
| Ephemeral question | `/btw` | Inline note + delete / scratchpad |
| Controlled summarize | `/compact <instructions>` | Summarize-and-restart with a focused prompt |
| Isolated side work | `/fork` / subagent | Spawn a separate agent/worktree |
| Specialized deep work | `/agents` + subagent | Delegate to a role-scoped agent |
| Inspect context | `/context` | Token/usage view if available |
| Roll back | `/rewind` | Checkpoint restore |
| Fresh start | `/clear` | New session/thread |

Names here are intentionally tool-agnostic so the skill stays useful as command surfaces evolve.
