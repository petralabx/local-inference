# Loop Routing Inventory

MC-Checkout: dsp_mr24bm9au2e44s

## Conclusion

The DGX Spark `llama.cpp` endpoint is proven as an OpenAI-compatible backend, but the broader repo ecosystem already has a canonical local inference control plane in `c:\Users\vince\local-inference` using LiteLLM.

The right production shape is:

```text
repo loops -> LiteLLM/local-inference proxy -> DGX Spark llama.cpp endpoint
```

This keeps existing consumers on the stable `local-primary` alias while letting the backend move from the older Qwen service to the DGX Spark cluster after GLM load gates pass.

## Current DGX Smoke Endpoint

```bash
OPENAI_BASE_URL=http://100.111.220.1:18081/v1
OPENAI_API_KEY=local-inference
LOCAL_INFERENCE_MODEL=smoke-qwen2.5-0.5b-rpc
```

This endpoint is for smoke testing only. It should not become the long-term URL hardcoded into repo loops.

## Existing Canonical Proxy

Repo:

```text
c:\Users\vince\local-inference
```

Current known contract:

```bash
OPENAI_BASE_URL=http://100.103.33.54:4000/v1
LOCAL_INFERENCE_MODEL=local-primary
```

Important files:

- `litellm/config.yaml`
- `litellm/config.dgx.example.yaml`
- `.env.example`
- `.env.local`
- `config/execution-primitives.local.yaml`
- `scripts/start_proxy.sh`
- `scripts/smoke_proxy.sh`
- `scripts/smoke_backend.sh`

Recommended change:

- Keep client repos pointed at LiteLLM.
- Add or update a DGX backend alias in `litellm/config.yaml`.
- Promote `local-primary` to the DGX GLM alias only after the GLM load gate passes.

## `agentic-swarm`

Repo:

```text
c:\Users\vince\agentic-swarm
```

Current routing facts:

- Stage Rail already supports OpenAI-compatible local escalation through:
  - `STAGE_RAIL_ESCALATION_BASE_URL`
  - `STAGE_RAIL_ESCALATION_API_KEY`
  - `STAGE_RAIL_ESCALATION_MODEL`
  - `STAGE_RAIL_ESCALATION_MAX_TOKENS`
  - `STAGE_RAIL_ESCALATION_TIMEOUT`
  - `STAGE_RAIL_ESCALATION_THINK`
- Swarm dispatch is not fully local-wired yet:
  - `config/models.yaml` has local aliases commented out.
  - `src/config.py` has no local provider branch.
- VMC autoresearch resolves Cursor-native model IDs through role files such as `eval/models.json`, not through OpenAI base URLs.

Recommended changes:

1. Route Stage Rail first by setting:

   ```bash
   STAGE_RAIL_ESCALATION_BASE_URL=http://100.103.33.54:4000/v1
   STAGE_RAIL_ESCALATION_MODEL=local-primary
   STAGE_RAIL_ESCALATION_API_KEY=$LOCAL_LITELLM_MASTER_KEY
   ```

2. Implement the pending `local-primary` provider branch in `src/config.py` before assigning general swarm agents to local models.
3. Uncomment/add local aliases in `config/models.yaml` only after the provider branch and smoke tests pass.
4. Leave Dawn/X and xAI-specific scripts on xAI unless a separate migration is planned.

## Cursor/VMC Loops

Cursor IDE agent selection and Cursor SDK role routing are not normal OpenAI-compatible environment consumers.

Recommended changes:

- Do not assume `OPENAI_BASE_URL` will reroute Cursor-native models.
- For SDK scripts that explicitly use OpenAI-compatible clients, point them at LiteLLM.
- For VMC autoresearch roles, treat local routing as a separate implementation task because model IDs are Cursor-native today.

## PLX Mission Control And Skills Repos

Repos:

```text
c:\Users\vince\PLX_MC
c:\Users\vince\plx-cursor-skills
c:\Users\vince\petra-lab-x-skills
```

Current routing facts:

- These repos mostly coordinate tasks, MCP, and skills.
- They do not appear to be primary LLM loop consumers.
- Azure OpenAI settings in `PLX_MC` are for a separate feature path.

Recommended changes:

- No direct DGX routing change until a specific MCP/tool path needs it.

## Path Drift Risks

There are multiple local checkouts:

- `c:\Users\vince\local-inference-2`
- `c:\Users\vince\local-inference`
- `c:\Users\vince\local-inference-1`
- `c:\Users\vince\agentic-swarm`
- `c:\Users\vince\Documents\GitHub\agentic-swarm`
- multiple `Documents\GitHub\agentic-swarm-*` worktrees

Recommended rule:

- Treat `c:\Users\vince\local-inference` as the current runtime control plane.
- Treat `c:\Users\vince\local-inference-2` as the DGX project/orchestration handoff until code is promoted.
- Confirm the active `agentic-swarm` checkout before editing loop code.

## Promotion Order

1. Keep DGX smoke endpoint alive for direct validation.
2. Finish GLM download, merge, and low-context load test.
3. Add DGX backend alias to `local-inference` LiteLLM config.
4. Run `local-inference` proxy smoke tests.
5. Route Stage Rail through `local-primary`.
6. Implement local provider support in `agentic-swarm` swarm dispatch.
7. Expand to broader loops only after each consumer has a passing smoke test.
