# Dell Qwen worker lane

Dell tower (`VTA`, Tailscale `100.103.33.54`) runs the **code/structure worker tier** behind LiteLLM.

Repository: [petralabx/local-inference](https://github.com/petralabx/local-inference).

## Aliases

| Alias | Backend | Use |
|-------|---------|-----|
| `local-primary` | Qwen3-32B-AWQ on Dell `:8000` | JSON, tools, medium context, general code worker |
| `local-fast` | Same as primary today | Reserved for smaller routing model |
| `local-coder` | Ornith-35B on Spark A `:18082` via this proxy | Code / Organizer fallback |
| `local-driver` | Qwen3.6-A3B on Spark B `:18090` via this proxy | Organizer classify |
| `local-glm52` | Retired on this proxy | Do not use for Organizer |

Proxy: `http://100.103.33.54:4000/v1` · key: `LOCAL_LITELLM_MASTER_KEY` in repo `.env.local`

Never curl `/v1/models` without `Authorization: Bearer $LOCAL_LITELLM_MASTER_KEY`. Unauthenticated list returns HTTP 500.

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

# Organizer aliases (must send the master key)
./scripts/smoke_organizer_aliases.sh
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

## Cross-platform one-shot client (Python 3.11+)

```powershell
# Windows PowerShell
$env:LOCAL_LITELLM_MASTER_KEY = "sk-local-..."
python scripts/ask_local_worker.py --model local-primary --prompt "Return strict JSON for this schema: ..."

# Fallback to a specific env file when LOCAL_LITELLM_MASTER_KEY is not exported
python scripts/ask_local_worker.py --model local-coder --env-file .env.local --prompt "Refactor this function for readability."
```

```bash
# Linux / cloud shell (same defaults and aliases)
export LOCAL_LITELLM_MASTER_KEY="sk-local-..."
python3 scripts/ask_local_worker.py --model local-glm52 --system "You are a concise release drafter." --prompt "Draft changelog bullets."

# Optional Tailscale userspace outbound HTTP proxy
python3 scripts/ask_local_worker.py --model local-primary --proxy http://127.0.0.1:1054 --prompt "Explain this traceback."
```

The standard-library client accepts only HTTP/HTTPS proxy URLs. It does not
implement SOCKS transport.

See also: `docs/runbooks/cursor-orchestrator-worker.md`

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `local-primary` chat fails | Run `start_dell_qwen_stack.ps1`; check `docker logs vllm-local-primary` |
| `local-coder` 404 / wrong model | Run `swap_dell_qwen_coder.ps1` — container must match alias |
| Proxy `/health` errors | Ignore if `/v1/models` + chat work with master key |
| Proxy missing `local-coder` | Run `restart_litellm_proxy.ps1` after config change |
