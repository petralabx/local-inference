# DGX Spark Local Inference Operations

MC-Checkout: dsp_mr24bm9au2e44s

## Hosts

| Role | Host | Tailnet | CX-7 | User |
| --- | --- | --- | --- | --- |
| Coordinator | `phase-f-dgx-spark` / `spark-7d3d` | `100.111.220.1` | `192.168.100.10` | `vinnysachet` |
| RPC worker | `spark-b4ec` | `100.92.253.61` | `192.168.100.11` | `vinnysachet2` |

## Current Smoke Services

Single-node smoke server:

```text
http://100.111.220.1:18080/v1
model: smoke-qwen2.5-0.5b
```

Two-node RPC smoke server:

```text
http://100.111.220.1:18081/v1
model: smoke-qwen2.5-0.5b-rpc
```

RPC worker:

```text
spark-b4ec:50052
CX-7 path: 192.168.100.11:50052
```

## Health Checks

From Windows / Cursor host:

```powershell
Invoke-RestMethod -Uri "http://100.111.220.1:18081/v1/models" | ConvertTo-Json -Depth 8
```

Chat smoke:

```powershell
$body = @{
  model = "smoke-qwen2.5-0.5b-rpc"
  messages = @(@{ role = "user"; content = "Reply with exactly: local inference online" })
  max_tokens = 16
  temperature = 0
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Uri "http://100.111.220.1:18081/v1/chat/completions" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## Logs

Coordinator:

```bash
~/logs/llama-smoke-server-18080.log
~/logs/llama-rpc-smoke-server-18081.log
~/logs/download-glm52-ud-iq1m.log
```

Worker:

```bash
~/logs/ggml-rpc-server.log
```

## Restart RPC Worker

On `spark-b4ec`:

```bash
pkill -x ggml-rpc-server || true
cd ~/src/llama.cpp
nohup build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052 > ~/logs/ggml-rpc-server.log 2>&1 &
echo $! > ~/logs/ggml-rpc-server.pid
```

## Restart RPC Smoke Server

On `spark-7d3d`:

```bash
cd ~/src/llama.cpp
nohup build/bin/llama-server \
  -m ~/models/smoke/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --alias smoke-qwen2.5-0.5b-rpc \
  --host 0.0.0.0 \
  --port 18081 \
  --rpc 192.168.100.11:50052 \
  -ngl 99 \
  -c 2048 \
  > ~/logs/llama-rpc-smoke-server-18081.log 2>&1 &
echo $! > ~/logs/llama-rpc-smoke-server-18081.pid
```

## GLM Download

Download script:

```bash
~/scripts/download-glm52-ud-iq1m.sh
```

Progress:

```bash
tail -f ~/logs/download-glm52-ud-iq1m.log
ls -lh ~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/UD-IQ1_M/
```

The download uses `curl -C -`, so rerunning the script resumes partial files.

Merge script:

```bash
~/scripts/merge-glm52-ud-iq1m.sh
```

This script refuses to run until all six split files exist and are non-empty. It writes:

```text
~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf
~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf.sha256
```

Low-context GLM load gate:

```bash
~/scripts/load-gate-glm52-ud-iq1m.sh
```

It starts:

```text
http://100.111.220.1:18082/v1
model: local-glm52-ud-iq1m
ctx: 8192
parallel: 1
rpc worker: 192.168.100.11:50052
```

Check logs:

```bash
tail -f ~/logs/llama-glm52-ud-iq1m-18082.log
```

## GLM Runtime Settings (decided by benchmark)

The GLM server runs with reasoning disabled at the server level, so every client
(direct or via the LiteLLM proxy) gets thinking-off by default:

```bash
build/bin/llama-server \
  -m ~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf \
  --alias local-glm52-ud-iq1m \
  --host 0.0.0.0 --port 18082 \
  --rpc 192.168.100.11:50052 \
  -ngl 99 -c 4096 --parallel 1 \
  --reasoning off --reasoning-budget 0
```

Benchmark findings on this UD-IQ1_M / two-node RoCE setup:

- Reasoning ON burned the entire token budget on `reasoning_content` and emitted
  no code (415s / 3000 tokens / 0 chars content). Reasoning OFF produced correct
  code in 15-91s. Reasoning is therefore disabled by default.
- MTP speculative decoding (`--spec-type draft-mtp --spec-draft-n-max 2`)
  regressed decode from ~7.4 tok/s to ~5.1 tok/s on the two-node split. MTP is
  NOT used. Published MTP speedups are single-node; the cross-node draft/verify
  round trips outweigh the benefit here.
- Baseline decode ceiling: ~7.4 tok/s at UD-IQ1_M.

## Boot Durability (systemd)

Both nodes have systemd units installed and enabled for boot (survive reboot).
They are syntax-verified (`systemd-analyze verify`) and enabled, but the live GLM
is still the original `nohup` process until a one-time cutover is done (cutover
forces a ~15-20 min model reload).

Worker (`spark-b4ec`): `/etc/systemd/system/ggml-rpc.service`

```bash
sudo systemctl status ggml-rpc.service
sudo systemctl start ggml-rpc.service     # binds 192.168.100.11:50052
sudo journalctl -u ggml-rpc.service -f
```

Coordinator (`spark-7d3d`): `/etc/systemd/system/glm-server.service`

```bash
sudo systemctl status glm-server.service
sudo systemctl start glm-server.service   # loads GLM, ~15-20 min, port 18082
sudo journalctl -u glm-server.service -f
```

### One-time validated cutover (recommended before relying on reboot recovery)

An enabled-but-never-started unit is unproven. To validate and switch the live
stack onto systemd (costs one ~15-20 min GLM reload):

```bash
# 1. worker first (on spark-b4ec)
kill "$(cat ~/logs/ggml-rpc-server.pid)" 2>/dev/null || true
sudo systemctl start ggml-rpc.service

# 2. coordinator (on spark-7d3d)
kill "$(cat ~/logs/llama-glm52-ud-iq1m-18082.pid)" 2>/dev/null || true
sudo systemctl start glm-server.service

# 3. wait for load, then verify
curl -s http://127.0.0.1:18082/health
```

Boot ordering across machines is not guaranteed; the coordinator unit uses
`Restart=on-failure` so it retries until the worker's RPC port is reachable.

## Temporary Sudo

Temporary passwordless sudo was added for setup:

```text
/etc/sudoers.d/99-cursor-setup
```

Remove after the final service/install state is stable:

```bash
sudo rm /etc/sudoers.d/99-cursor-setup
```

Do not remove it before durable services and any needed systemd units are finalized.
