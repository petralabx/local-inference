# DGX Spark GLM Cluster Evidence

MC-Checkout: dsp_mr24bm9au2e44s

## Phase 1: Durable CX-7 Networking

Status: PASS

Date: 2026-07-01

Configured both DGX Spark systems through NetworkManager, not direct netplan edits, because both nodes use NetworkManager as the active renderer and already had `enp1s0f1np1` connection profiles.

### `phase-f-dgx-spark` / `spark-7d3d`

- Tailnet: `100.111.220.1`
- SSH user: `vinnysachet`
- CX-7 interface: `enp1s0f1np1`
- NetworkManager connection: `enp1s0f1np1`
- IPv4 method: `manual`
- IPv4 address: `192.168.100.10/24`
- Autoconnect: `yes`
- Never default route: `yes`
- IPv6 method: `ignore`

Verification:

```text
enp1s0f1np1      UP             192.168.100.10/24 fe80::4ebb:47ff:fe2f:7d3f/64
PING 192.168.100.11: 3 transmitted, 3 received, 0% packet loss
rtt min/avg/max/mdev = 0.265/0.510/0.880/0.266 ms
```

### `spark-b4ec`

- Tailnet: `100.92.253.61`
- SSH user: `vinnysachet2`
- CX-7 interface: `enp1s0f1np1`
- NetworkManager connection: `enp1s0f1np1`
- IPv4 method: `manual`
- IPv4 address: `192.168.100.11/24`
- Autoconnect: `yes`
- Never default route: `yes`
- IPv6 method: `ignore`

Verification:

```text
enp1s0f1np1      UP             192.168.100.11/24 fe80::4ebb:47ff:fe2a:b4ee/64
PING 192.168.100.10: 3 transmitted, 3 received, 0% packet loss
rtt min/avg/max/mdev = 0.548/0.936/1.157/0.275 ms
```

### Phase 1 Commands

`spark-7d3d`:

```bash
sudo nmcli connection modify enp1s0f1np1 \
  ipv4.method manual \
  ipv4.addresses 192.168.100.10/24 \
  ipv4.never-default yes \
  ipv6.method ignore \
  connection.autoconnect yes
sudo nmcli connection up enp1s0f1np1
```

## Phase 2: `llama.cpp` CUDA/RPC Build

Status: PASS

Date: 2026-07-01

Built the same `llama.cpp` commit on both nodes:

```text
4fc4ec5541b243957ae5099edb67372f8f3b550e
```

Native build settings:

```bash
cmake -S . -B build \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=121 \
  -DCMAKE_BUILD_TYPE=Release
```

Built tools:

- `build/bin/llama-server`
- `build/bin/ggml-rpc-server`
- `build/bin/llama-cli`
- `build/bin/llama-gguf-split`

Note: upstream target name is `ggml-rpc-server`, not `rpc-server`.

CUDA verification from `ggml-rpc-server --help` on both nodes:

```text
ggml_cuda_init: found 1 CUDA devices (Total VRAM: 124609-124610 MiB):
  Device 0: NVIDIA GB10, compute capability 12.1, VMM: yes
```

Docker was not used because both users lack permission for `/var/run/docker.sock`; native CUDA toolkit exists at `/usr/local/cuda-13.0/bin/nvcc`.

## Phase 3: Single-Node Small-Model Smoke

Status: PASS

Date: 2026-07-01

Coordinator: `spark-7d3d` / `phase-f-dgx-spark`

Smoke model:

- Repo: `Qwen/Qwen2.5-0.5B-Instruct-GGUF`
- File: `qwen2.5-0.5b-instruct-q4_k_m.gguf`
- Local path: `/home/vinnysachet/models/smoke/qwen2.5-0.5b-instruct-q4_k_m.gguf`
- Size: `469M`
- SHA-256: `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`

Server:

```bash
build/bin/llama-server \
  -m /home/vinnysachet/models/smoke/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --alias smoke-qwen2.5-0.5b \
  --host 0.0.0.0 \
  --port 18080 \
  -ngl 99 \
  -c 2048
```

Startup evidence:

```text
model loaded
listening on http://0.0.0.0:18080
```

OpenAI-compatible endpoint evidence:

- `GET http://100.111.220.1:18080/v1/models` returned `smoke-qwen2.5-0.5b`.
- `POST http://100.111.220.1:18080/v1/chat/completions` returned:

```text
local inference online
```

Timing snapshot:

```text
prompt_per_second: 1019.3968568596914
predicted_per_second: 364.1660597232338
```

## Phase 4: Two-Node RPC Smoke

Status: PASS

Date: 2026-07-01

Worker: `spark-b4ec`

RPC worker command:

```bash
build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052
```

Worker startup evidence:

```text
ggml_cuda_init: found 1 CUDA devices (Total VRAM: 124609 MiB):
  Device 0: NVIDIA GB10, compute capability 12.1, VMM: yes, VRAM: 124609 MiB
ggml_backend_cuda_get_available_uma_memory: final available_memory_kb: 120194492
```

Coordinator: `spark-7d3d` / `phase-f-dgx-spark`

RPC-backed server command:

```bash
build/bin/llama-server \
  -m /home/vinnysachet/models/smoke/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --alias smoke-qwen2.5-0.5b-rpc \
  --host 0.0.0.0 \
  --port 18081 \
  --rpc 192.168.100.11:50052 \
  -ngl 99 \
  -c 2048
```

OpenAI-compatible endpoint evidence:

- `GET http://100.111.220.1:18081/v1/models` returned `smoke-qwen2.5-0.5b-rpc`.
- `POST http://100.111.220.1:18081/v1/chat/completions` returned text through the RPC-backed endpoint.

Timing snapshot:

```text
prompt_per_second: 656.5522136456393
predicted_per_second: 351.3626281924589
```

RPC/RDMA evidence from worker:

```text
Accepted client connection
RDMA probed: dev=rocep1s0f1 gid=3 RoCEv2
RDMA activated: qpn=... mtu=1024 rx_depth=24
ggml_backend_cuda_graph_compute: CUDA graph warmup complete
```

## Phase 5: LiteLLM Control-Plane Smoke

Status: PASS

Date: 2026-07-01

Control-plane repo:

```text
c:\Users\vince\local-inference
```

Added a non-disruptive LiteLLM alias:

```yaml
- model_name: local-dgx-smoke
  litellm_params:
    model: openai/smoke-qwen2.5-0.5b-rpc
    api_base: http://100.111.220.1:18081/v1
    api_key: local-inference
```

`local-primary` and `local-fast` were left unchanged. The DGX smoke alias is only a proof path until GLM passes its load gate.

Proxy:

```text
http://127.0.0.1:4000/v1
http://100.103.33.54:4000/v1
```

Verified through LiteLLM:

- `/v1/models` exposed `local-primary`, `local-fast`, and `local-dgx-smoke`.
- `POST /v1/chat/completions` with `model=local-dgx-smoke` returned:

```text
1+1 equals 2.
```

Startup script note:

- `scripts/start_proxy.sh` had CRLF-sensitive Bash parsing.
- It was simplified and validated with `bash -n scripts/start_proxy.sh`.

## Phase 7: GLM UD-IQ1_M Merge + Two-Node Load Gate

Status: PASS

Date: 2026-07-02

### Download

All six `UD-IQ1_M` splits downloaded to the coordinator (resumable `curl -C -`), total ~215 GiB. Log ended with `all split downloads complete`.

### Merge

```bash
build/bin/llama-gguf-split --merge \
  ~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/UD-IQ1_M/GLM-5.2-UD-IQ1_M-00001-of-00006.gguf \
  ~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf
```

Result:

```text
merged from 6 split with 1809 tensors
GLM-5.2-UD-IQ1_M.gguf  216 GB
sha256: 5828b3bbe319d3ad23dba124880b4c5a129d8d4b4d7a3844b739c4a7192bc995
```

### Load gate

```bash
build/bin/llama-server \
  -m ~/models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf \
  --alias local-glm52-ud-iq1m \
  --host 0.0.0.0 --port 18082 \
  --rpc 192.168.100.11:50052 \
  -ngl 99 -c 4096 --parallel 1
```

- Load time: ~19 minutes across both nodes (weights streamed to both GB10 unified-memory pools; coordinator + worker each filled to ~107-120 GiB, coordinator used ~7.8 GiB swap).
- `/health` returned `{"status":"ok"}`.

### Generation evidence (direct, port 18082)

- First call confirmed generation; GLM-5.2 is a thinking model, so output populates `reasoning_content`.
- Full answer with `finish_reason: stop`: `Hello! The DGX Spark cluster is online.`
- Throughput: ~7.3 tokens/s decode, ~15 tokens/s prompt (UD-IQ1_M, TP over RoCE, single stream).

### Generation evidence (via LiteLLM proxy)

- Added alias `local-glm52` -> `http://100.111.220.1:18082/v1` in `local-inference/litellm/config.yaml`.
- Proxy `/v1/models` exposes: `local-primary, local-fast, local-dgx-smoke, local-glm52`.
- `POST /v1/chat/completions` with `model=local-glm52` returned, `finish_reason: stop`:
  `Hello! I am GLM, a large language model running locally.`

## Phase 7b: Reasoning + MTP Tuning (benchmark evidence)

Date: 2026-07-02

Same coding prompts, UD-IQ1_M, two-node RoCE, single stream.

### Reasoning on vs off

| Prompt | Reasoning | Wall | Output | Code? |
|---|---|---|---|---|
| merge_intervals | off | 15.3s | 107 tok | correct |
| longest_palindromic_substring | off | 91s | 425 tok | correct (minor sloppy 3rd assert) |
| longest_palindromic_substring | on | 414.6s | 3000 tok, 11,295 reasoning chars, 0 content | none (never finished thinking) |

Conclusion: at IQ1_M, reasoning-on is a net loss on both speed and yield. Disabled server-side with `--reasoning off --reasoning-budget 0`.

### MTP speculative decoding

GGUF contains MTP head (`blk.78.nextn.*`, kv `glm-dsa.nextn_predict_layers`); build supports `--spec-type draft-mtp`.

| Config | merge_intervals | Decode |
|---|---|---|
| No MTP | 15.3s / 107 tok | 7.45 tok/s |
| MTP n=2 | 20.8s / 98 tok | 5.09 tok/s |

Conclusion: MTP regressed ~30% on the two-node split (cross-node draft/verify overhead). Not used.

### Standing config

Server relaunched with `--reasoning off --reasoning-budget 0`, no MTP. Baseline decode ceiling ~7.4 tok/s. Verified reasoning-off end to end (empty `reasoning_content`, clean code) both direct (`:18082`) and via LiteLLM proxy (`local-glm52`).

## Phase 8: Boot Durability

Status: PARTIAL (installed + enabled; cutover pending by operator choice)

Date: 2026-07-02

- Worker unit `/etc/systemd/system/ggml-rpc.service` on `spark-b4ec`: written, `systemd-analyze verify` OK, `systemctl enable` done.
- Coordinator unit `/etc/systemd/system/glm-server.service` on `spark-7d3d`: written, verified, enabled. Carries `--reasoning off --reasoning-budget 0`.
- Both enabled for boot (multi-user.target symlinks created).
- Live stack still runs as the original `nohup` processes; the one-time validated cutover (which forces a ~15-20 min GLM reload) is left to operator timing. See OPERATIONS.md.
- Temporary sudo (`/etc/sudoers.d/99-cursor-setup`) still present on both nodes; retained because setup work (cutover, potential quant experiments, 3rd-node prep) is ongoing.

`spark-b4ec`:

```bash
sudo nmcli connection modify enp1s0f1np1 \
  ipv4.method manual \
  ipv4.addresses 192.168.100.11/24 \
  ipv4.never-default yes \
  ipv6.method ignore \
  connection.autoconnect yes
sudo nmcli connection up enp1s0f1np1
```
