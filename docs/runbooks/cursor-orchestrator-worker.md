# Cursor orchestrator / local worker routing

Use **frontier Cursor models** (Fable 5, Composer 2.5, Claude) as the **orchestrator**. Use **LiteLLM worker aliases** for generation passes — never enable global OpenAI override on the Default Cursor profile.

Repo: [petralabx/local-inference](https://github.com/petralabx/local-inference)

## Worker tiers

| Tier | Alias | Use |
|------|-------|-----|
| L4 | `local-glm52` | Prose, drafts, loop summaries |
| L2 | `local-primary` | JSON, debug hypotheses, structure |
| L3 | `local-coder` | Code patches (after Dell container swap) |

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ask_local_worker.ps1 -Model local-primary -Prompt "..."
```

## Cursor profiles (one-time)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_cursor_profiles_local_glm.ps1
```

- **Default profile** — frontier models only; no OpenAI override
- **Local GLM profile** — `local-glm52` only for long local-only sessions

Rollback: `python scripts/revert_cursor_local_glm52.py` then restart Cursor.

## Operator files (machine-local)

Back up or version separately (not in this repo):

- `~/.cursor/rules/local-glm-routing.mdc`
- `~/.cursor/AGENTS.md`
- `~/.cursor/agents/local-{drafter,loop-worker,researcher}.md`
- `~/.cursor/skills/loop/SKILL.md` (orchestrator/worker section)

## Loop pattern

```text
/loop tick → orchestrator (frontier) gathers facts
          → worker (L4/L2/L3) via ask_local_worker.ps1
          → orchestrator reviews, edits, tests, next tick
```
