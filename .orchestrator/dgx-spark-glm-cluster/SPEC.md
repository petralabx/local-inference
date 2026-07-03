---
slug: dgx-spark-glm-cluster
created: 2026-07-01
status: approved-for-execution
mc_task: TASK-246
mc_checkout: dsp_mr24bm9au2e44s
owner: local-inference
---

# DGX Spark GLM 5.2 GGUF Local Inference Spec

MC-Checkout: dsp_mr24bm9au2e44s

## Objective

Bring up a first-class local inference service across two DGX Spark systems so PLX repo automation loops can target a stable local OpenAI-compatible endpoint before the large GLM GGUF model is attempted.

Target model: `huihui-ai/Huihui-GLM-5.2-abliterated-GGUF`, starting with `UD-IQ1_M`.

Target serving path: `llama.cpp` with CUDA and RPC, not Ray/vLLM, because the selected model artifact is GGUF.

## Current Cluster Facts

- Coordinator candidate: `phase-f-dgx-spark` / `spark-7d3d`, Tailnet `100.111.220.1`, Linux user `vinnysachet`.
- Worker candidate: `spark-b4ec`, Tailnet `100.92.253.61`, Linux user `vinnysachet2`.
- Direct CX-7 interface on both nodes: `enp1s0f1np1`.
- Temporary CX-7 IPs already proven:
  - `spark-7d3d`: `192.168.100.10/24`
  - `spark-b4ec`: `192.168.100.11/24`
- Direct ping works both ways with 0% packet loss and sub-millisecond to ~1 ms RTT.
- NetworkManager is the active renderer, so durable CX-7 configuration should use `nmcli`, not a blind netplan drop-in.

## Non-Goals

- Do not create an NVIDIA Sync cluster unless later evidence shows it is required.
- Do not use Ray/vLLM for the selected GGUF target.
- Do not expose the abliterated model publicly.
- Do not attempt 1M context on two Sparks.
- Do not download the 231 GB model until small-model and RPC gates pass.

## Architecture

```text
repo loops / Cursor agents
        |
        | OPENAI_BASE_URL=http://<coordinator-tailnet>:8080/v1
        v
spark-7d3d / phase-f-dgx-spark
  llama-server coordinator
  merged GGUF stored locally
  local GB10 backend
        |
        | TCP over CX-7: 192.168.100.0/24
        v
spark-b4ec
  llama.cpp rpc-server worker
  remote GB10 backend
```

## Phase Plan

### Phase 1: Durable CX-7 Networking

Use NetworkManager to persist `enp1s0f1np1` addresses:

- `spark-7d3d`: `192.168.100.10/24`
- `spark-b4ec`: `192.168.100.11/24`

Acceptance evidence:

- `nmcli connection show enp1s0f1np1` shows manual IPv4 address on both nodes.
- `ping -c 3` succeeds both directions over `192.168.100.0/24`.

### Phase 2: Build `llama.cpp`

Build the same `llama.cpp` commit on both Sparks with CUDA and RPC support.

Acceptance evidence:

- `llama-server --help` runs on coordinator.
- `rpc-server --help` runs on worker.
- Build commit recorded in evidence.

### Phase 3: Single-Node Small-Model Smoke

Download a small GGUF model on the coordinator and run `llama-server` without RPC.

Acceptance evidence:

- `/v1/models` responds.
- A short `/v1/chat/completions` or `/completion` request returns text.

### Phase 4: Two-Node RPC Smoke

Run `rpc-server` on `spark-b4ec` and `llama-server --rpc 192.168.100.11:50052` on the coordinator with the small model.

Acceptance evidence:

- `rpc-server` accepts connection from coordinator.
- `llama-server` loads and responds through the endpoint.
- Logs show RPC backend/device participation.

### Phase 5: Endpoint Contract For Loops

Define a stable contract for downstream repos:

- `OPENAI_BASE_URL=http://100.111.220.1:8080/v1` or Tailnet DNS equivalent.
- `OPENAI_API_KEY` local placeholder/token.
- `LOCAL_INFERENCE_MODEL=<served-model-alias>`.

Acceptance evidence:

- Documented environment contract.
- At least one local curl/OpenAI-compatible request succeeds.

### Phase 6: Cross-Repo Loop Routing Investigation

Inventory local PLX repos and identify how each loop chooses model endpoints.

Acceptance evidence:

- `LOOP_ROUTING.md` lists repos, model config files/env vars, current defaults, and required changes.
- No repo is modified until routing contract is confirmed.

### Phase 7: Large GLM GGUF Prep And Load Gate

Only after prior gates pass, download and merge `UD-IQ1_M`.

Acceptance evidence:

- Free disk checked before download.
- Split download and merged output paths recorded.
- Low-context load test attempted first (`--ctx-size 8192`, `--parallel 1`).
- Result classified as pass, blocked, or needs smaller/pruned model.

### Phase 8: Cleanup And Operations

Document durable operations and remove temporary privileged access if no longer required.

Acceptance evidence:

- `OPERATIONS.md` includes start/stop, health check, endpoint, and rollback.
- Temporary sudoers files either removed or explicitly retained with rationale.

## Safety And Governance

- The target model is abliterated/uncensored. Use only for controlled local research and coding loops.
- Keep endpoint Tailnet/private only.
- Keep large-model work gated by small-model proof.
- Record all remote changes in `.orchestrator/dgx-spark-glm-cluster/EVIDENCE.md`.

## Execution State

- `RESEARCH.md` complete and aligned to GGUF/llama.cpp.
- Phase 1 ready to execute.
