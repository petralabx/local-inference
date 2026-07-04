# Dell Qwen worker lane

Dell tower (`VTA`, Tailscale `100.103.33.54`) runs the **code/structure worker tier** behind LiteLLM.

Repo: [petralabx/local-inference](https://github.com/petralabx/local-inference) (dev: `taylorvalton/local-inference`).

## Aliases

| Alias | Backend | Use |
|-------|---------|-----|
| `local-primary` | Qwen3-32B-AWQ on Dell `:8000` | JSON, tools, medium context, general code worker |
| `local-coder` | Qwen3-Coder-30B-FP8 on Dell `:8000` | Code fixes, refactors (swap container first) |
| `local-fast` | Same as primary today | Reserved for smaller routing model |
| `local-glm52` | DGX GLM `:18082` | Prose, drafts, loop worker text |

Proxy: `http://100.103.33.54:4000/v1` · key: `LOCAL_LITELLM_MASTER_KEY` in repo `.env.local`

## Start / verify (on Dell)

From the repo root (`local-inference` checkout):

```powershell
# 1. vLLM backend (durable, survives Docker restart)
powershell -ExecutionPolicy Bypass -File scripts/start_dell_qwen_stack.ps1

# 2. LiteLLM proxy (Git Bash on Dell)
./scripts/start_proxy.sh

# Or PowerShell restart (picks up config.yaml changes):
powershell -ExecutionPolicy Bypass -File scripts/restart_litellm_proxy.ps1

# 3. Health + chat smoke
powershell -ExecutionPolicy Bypass -File scripts/health_check_local_inference.ps1 -SmokeChat
```

## Swap to Coder model

Only one large model fits on the RTX PRO 5000 at a time:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/swap_dell_qwen_coder.ps1
# ... use local-coder ...
powershell -ExecutionPolicy Bypass -File scripts/start_dell_qwen_stack.ps1
```

## Invoke from Cursor orchestrator sessions

```powershell
# Code / JSON / debug hypothesis (L2)
powershell -ExecutionPolicy Bypass -File scripts/ask_local_worker.ps1 -Model local-primary -Prompt "..."

# Code worker after swap (L3)
powershell -ExecutionPolicy Bypass -File scripts/ask_local_worker.ps1 -Model local-coder -Prompt "..."

# Prose / drafts (L4, DGX)
powershell -ExecutionPolicy Bypass -File scripts/ask_local_worker.ps1 -Model local-glm52 -Prompt "..."
```

Qwen models append `/no_think` automatically; thinking blocks are stripped from output.

See also: `docs/runbooks/cursor-orchestrator-worker.md`

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `local-primary` chat fails | Run `start_dell_qwen_stack.ps1`; check `docker logs vllm-local-primary` |
| `local-coder` 404 / wrong model | Run `swap_dell_qwen_coder.ps1` — container must match alias |
| Proxy `/health` errors | Ignore if `/v1/models` + chat work with master key |
| Proxy missing `local-coder` | Run `restart_litellm_proxy.ps1` after config change |
