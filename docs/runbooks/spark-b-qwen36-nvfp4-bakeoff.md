# Spark B Qwen3.6 NVFP4+MTP bake-off

**Status:** bake-off only. Live aliases are unchanged.  
**Accountable:** Vince · operator `cos@petrasoap.com`  
**Node:** Spark B `spark-b4ec` / Tailscale `100.92.253.61` / SSH `vinnysachet2`

Vince requires **uncensored / abliterated** weights. Do **not** use
`nvidia/Qwen3.6-35B-A3B-NVFP4` (stock). Preferred checkpoint:

`THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP` (Huihui lineage, NVFP4 + MTP).

Reported ~95 tok/s on DGX Spark with MTP=3. This runbook does not download
weights from a Cloud Agent VM and does not SSH to Sparks.

## Current live (do not cut over)

| Alias | Backend | Port |
|-------|---------|------|
| `local-coder` | Spark A llama.cpp GGUF Ornith-35B | `100.111.220.1:18082` |
| `local-driver` | Spark B llama.cpp GGUF Qwen3.6-35B-A3B | `100.92.253.61:18090` |
| `local-primary` / `local-fast` | Dell Qwen3-32B-AWQ vLLM | `127.0.0.1:8000` |
| `local-driver-nvfp4` | **not in live** — optional example alias | `100.92.253.61:18091` |

Dell `:8000` is a later deprecation **after** this bake-off is signed off. Keep
GGUF on `:18090` as rollback for the whole bake-off.

## 1. Download on Spark B (never on Dell)

On `spark-b4ec` as `vinnysachet2`:

```bash
mkdir -p ~/models/THe-Plague
hf download THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP \
  --local-dir ~/models/THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP
```

If `hf` is missing, use `huggingface-cli download` with the same `--local-dir`.
Do not pull this checkpoint onto the Dell tower.

## 2. Serve the side lane

From a `local-inference` checkout **on Spark B**:

```bash
bash scripts/start_spark_b_vllm_qwen36_nvfp4_mtp.sh
```

The script:

- binds **:18091 only**
- uses `--kv-cache-dtype fp8`, MTP `num_speculative_tokens=3`, prefix caching
- does **not** pass `--enforce-eager`
- refuses stock NVIDIA NVFP4 and refuses to bind `:18090`
- does not stop llama.cpp on `:18090`

`gpu-memory-utilization` defaults to `0.45` so GGUF rollback can stay resident
on the same GB10. Raise it only if you have measured headroom.

Dry-run (prints the command, starts nothing):

```bash
SPARK_B_OK=1 bash scripts/start_spark_b_vllm_qwen36_nvfp4_mtp.sh --dry-run
```

## 3. Smoke (backend, then optional proxy alias)

Direct bake-off backend:

```bash
curl -sS http://100.92.253.61:18091/v1/models

curl -sS http://100.92.253.61:18091/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":16,"temperature":0}'
```

Confirm rollback GGUF is still up:

```bash
curl -sS http://100.92.253.61:18090/v1/models
```

Optional LiteLLM alias: copy **only** the `local-driver-nvfp4` block from
`litellm/config.spark-b-nvfp4.example.yaml` into `litellm/config.yaml`, restart
the Dell proxy, then:

```bash
# Load LOCAL_LITELLM_MASTER_KEY from Dell .env.local — do not invent a key.
# Unauthenticated GET /v1/models is HTTP 500 even though
# allow_requests_on_db_unavailable: true is already set in live config
# ("No connected db" / missing Bearer). Always send the master key.
curl -sS http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LOCAL_LITELLM_MASTER_KEY}"

curl -sS http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${LOCAL_LITELLM_MASTER_KEY}" \
  -d '{"model":"local-driver-nvfp4","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":16,"temperature":0}'
```

Do not point loops at Spark `:18091` as a client contract. Clients stay on
`http://100.103.33.54:4000/v1`.

## 4. Rollback

Keep `:18090` llama.cpp GGUF running. If the NVFP4 lane misbehaves:

1. Stop only the bake-off process/container `vllm-spark-b-nvfp4-bakeoff` on Spark B.
2. Leave `:18090` alone.
3. Do not delete `local-driver` from `litellm/config.yaml`.
4. If you added `local-driver-nvfp4`, remove that block and restart the proxy.

## LiteLLM HTTP 500 note

Live `litellm/config.yaml` already has:

- `master_key: os.environ/LITELLM_MASTER_KEY` (from `LOCAL_LITELLM_MASTER_KEY` via `scripts/start_proxy.sh`)
- `allow_requests_on_db_unavailable: true`

That setting does **not** make an unauthenticated `/v1/models` succeed. Call
`/v1/models` with `Authorization: Bearer $LOCAL_LITELLM_MASTER_KEY`. There is
no one-line config change left to invent; do not hardcode a key.

## Dry checklist (this PR)

- [ ] Live `local-driver` still `http://100.92.253.61:18090/v1`
- [ ] Live `local-coder` still `http://100.111.220.1:18082/v1`
- [ ] Live `local-primary` still Dell `:8000` (not cut over here)
- [ ] Bake-off serve port is `:18091`, not `:18090`
- [ ] Example yaml adds `local-driver-nvfp4` without replacing `local-driver`
- [ ] Stock `nvidia/Qwen3.6-35B-A3B-NVFP4` is not referenced as the serve target
- [ ] Weights are downloaded on Spark B, not Dell
- [ ] Rollback = keep GGUF on `:18090`

## After bake-off (FUTURE PR — do not do this now)

When Vince signs off NVFP4 and Dell `:8000` is deprecated:

1. Promote `local-driver` → `:18091` only in a dedicated PR after bake-off evidence.
2. Keep `:18090` GGUF as rollback until that PR is proven.
3. `POST_CUTOVER_DO_NOT_LEAVE_LOCAL_PRIMARY_ON_DELL` — `local-primary` must move
   off `http://127.0.0.1:8000/v1`. Do not keep Dell AWQ as primary after that
   deprecation.
4. Do not point `local-primary` at Spark B `:18091` (driver lane, not primary).
5. Do not point `local-primary` at Spark B `:18090` either.

## Related

- Fleet inventory: `docs/runbooks/dgx-spark-fleet.md`
- Worker aliases: `docs/runbooks/dell-qwen-worker-lane.md`
- Example overlay: `litellm/config.spark-b-nvfp4.example.yaml`
- Serve script: `scripts/start_spark_b_vllm_qwen36_nvfp4_mtp.sh`
