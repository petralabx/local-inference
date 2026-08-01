# Control-plane boundaries — local-inference

**Audience:** operators and agents changing LiteLLM, vLLM, or DGX routing.  
**Tier:** tooling (`petralabx/local-inference`).  
**Owner:** Vince · **Effective:** 2026-07-23

Companion: [`dgx-spark-fleet.md`](dgx-spark-fleet.md), [`dell-qwen-worker-lane.md`](dell-qwen-worker-lane.md).

## Owner

| Role | Identity |
|------|----------|
| Accountable human | `vince@petrasoap.com` |
| Agent operator email (MC) | `cos@petrasoap.com` |
| MC default bucket (routing) | `BKT-INFRA` |

## Auth source

| Surface | Auth |
|---------|------|
| LiteLLM proxy (`:4000`) | Master key from `LOCAL_LITELLM_MASTER_KEY` in `.env.local` (gitignored). Never hardcode in `litellm/config.yaml`. |
| MC compliance gate | OIDC preferred; break-glass `COMPLIANCE_CI_TOKEN` repo secret |
| MC MCP (agents) | `MC_MCP_API_KEY` / Team MCP `x-api-key` — see PLX_MC FLEET-SECRETS-SOP |
| Clients | Call the Dell proxy only — never Spark `:8000` directly |

## Default state

| Alias | Backend intent |
|-------|----------------|
| `local-primary` | Dell Qwen worker (tools/JSON/code) |
| `local-coder` | Dell Qwen coder lane (swap container first) |
| `local-fast` | Fallback alias on Dell |
| `local-glm52` / `local-glm52-experimental` | DGX Spark GLM via Dell proxy |
| Durable proxy URL | `http://100.103.33.54:4000/v1` (Tailscale) |

## Kill switches

| Switch | Effect |
|--------|--------|
| Stop LiteLLM proxy / vLLM containers on Dell | All aliases unavailable |
| Remove or blank `LOCAL_LITELLM_MASTER_KEY` | Proxy rejects authenticated clients |
| `COMPLIANCE_MODE=soft` (repo variable) | Compliance warns only |
| Unset `PLX_MC_BASE_URL` | Compliance workflow skips (emergency) |
| `PLX_MC_ROUTING_METADATA_ENABLED=0` | Routing metadata job skips; compliance unchanged |
| Point `litellm/config.yaml` backends off | Individual alias drain without killing proxy |

## Health checks

```bash
# From a machine on the tailnet
curl -sS http://100.103.33.54:4000/v1/models | head
./scripts/smoke_proxy.sh
./scripts/smoke_backend.sh   # when run on the Dell against :8000
```

PowerShell operators: `scripts/health_check_local_inference.ps1`.

## Fallback

1. Prefer Tailscale proxy URL over LAN (`192.168.2.12` can move after router changes).
2. If DGX GLM is down, keep Dell `local-primary` / `local-fast` for structured work.
3. High-blast-radius decisions: keep frontier subscriptions available (see `docs/HERMES_PROVIDER.md`).
4. Never run GLM on the Dell tower; never loop agents at Spark `:8000`.

## Audit / data boundary

- No vendor API keys in this repo — local proxy master key only (`.env.local`).
- Do not commit `.env*`, secrets, or live master keys.
- Orchestrator evidence under `.orchestrator/` is promoted intentionally, not by default.
- Develop in `taylorvalton/local-inference-dev`; promote tracked files to this canonical repo by copy (unrelated histories).
