---
slug: dgx-spark-glm-cluster
created: 2026-07-01
updated: 2026-07-01
status: execution-planned
rubric_score: 91
mc_task: TASK-246
mc_checkout: dsp_mr24bm9au2e44s
---

# DGX Spark GLM 5.2 GGUF Local Inference Research

MC-Checkout: dsp_mr24bm9au2e44s

## Mission and Context

Stand up two NVIDIA DGX Spark systems as a local inference cluster for the abliterated GGUF build referenced by Grok/X: `huihui-ai/Huihui-GLM-5.2-abliterated-GGUF`, starting with `UD-IQ1_M`, then expose the result as one OpenAI-compatible endpoint that repo automation loops can target consistently.

This supersedes the earlier assumption that the target was NVIDIA's full `nvidia/GLM-5.2-NVFP4` vLLM/SGLang checkpoint. The GGUF target changes the recommended serving path to `llama.cpp` with RPC, because GGUF is llama.cpp's native format and llama.cpp can expose remote CUDA devices over TCP through `rpc-server`.

The important framing is still that this is not a transparent, general-purpose "unified VRAM" pool. The practical feature is distributed local inference: one coordinator process loads/serves the model, one or more remote workers expose accelerator devices, and users see a single HTTP API endpoint.

Current observed devices:

- `phase-f-dgx-spark` / `spark-7d3d`: Tailscale `100.111.220.1`, online, ping from workstation ~4 ms. SSH works as `vinnysachet` with passwordless sudo after operator unlock.
- `spark-b4ec`: Tailscale `100.92.253.61`, online, ping from workstation ~108 ms. SSH works as `vinnysachet2` with passwordless sudo after operator unlock.
- `spark-b4ec` can Tailscale-ping `phase-f-dgx-spark` in ~7 ms.
- `spark-b4ec` reports `NVIDIA GB10`; `nvidia-smi` memory total returned `[N/A]`.
- `spark-b4ec` has ConnectX/RoCE devices `rocep1s0f0`, `rocep1s0f1`, `roceP2p1s0f0`, `roceP2p1s0f1`.
- `spark-b4ec` shows `enp1s0f1np1` and alias `enP2p1s0f1np1` as `UP`, matching the NVIDIA QSFP cable playbook.
- Temporary CX-7 IPv4 configuration has been applied and verified:
  - `spark-7d3d`: `enp1s0f1np1 = 192.168.100.10/24`
  - `spark-b4ec`: `enp1s0f1np1 = 192.168.100.11/24`
  - bidirectional ping succeeds with 0% packet loss and sub-millisecond to ~1 ms RTT.
- NetworkManager is the active netplan renderer on both nodes, and `nmcli` already has `enp1s0f1np1` connection profiles. Durable configuration should use `nmcli`, not a blind standalone netplan file.

## Internal Findings

This repository is currently a platform placeholder rather than a deployed inference router. The only root files are:

- `README.md`: identifies the repo as PLX local LLM inference runtime and tooling.
- `plx-brand.json`: declares `local-inference` as a PLX platform repo, with GitHub metadata `Petra-Lab-X/local-inference`.
- `AGENTS.md`: requires PLX Mission Control linkage.
- `scripts/check-brand-repo-structure.py`: unrelated brand-structure validator.

Implications:

- There is no existing model router, OpenAI proxy, model registry, health checker, or per-repo loop configuration to reuse.
- The first implementation phase should create the service boundary, not patch existing inference code.
- Mission Control accepted `TASK-246` in bucket `local-inference`, but rejected the GitHub repo slug as not in registry. Registry metadata should be reconciled before PR closeout.
- The repo should own reproducible scripts and docs for `llama.cpp` build/install, RPC workers, model download/merge, endpoint health checks, and downstream repo environment exports.

## External Findings

The target model is `huihui-ai/Huihui-GLM-5.2-abliterated-GGUF`. Its model card describes an uncensored/abliterated version of `zai-org/GLM-5.2`, produced by modifying GGUF files from `unsloth/GLM-5.2-GGUF`. The `UD-IQ1_M` quant is listed as 1-bit and about 231 GB. The card instructs users to download the split files with `huggingface-cli` and merge them with `llama-gguf-split`.

The Grok/X post describes the same target as an abliterated GLM-5.2 GGUF, 754B total / 40B active MoE, 1M context, with the lowest `UD-IQ1_M` quant around 231 GB and practical load requirements around 223-250 GB plus much more for large KV cache.

llama.cpp's RPC backend supports distributed inference by building every participating machine with `-DGGML_RPC=ON`, starting `rpc-server` on remote hosts, and passing one or more `--rpc host:port` entries to `llama-cli` or `llama-server` on the coordinator. The RPC backend distributes model weights and KV cache across local and remote devices in proportion to available memory by default, with `--tensor-split` available for manual control.

NVIDIA's DGX Spark stacking guidance says two Sparks should be connected through the rear ConnectX-7 QSFP/CX7 ports using the approved QSFP/CX7 cable. The objective is distributed workloads across Grace Blackwell GPUs using MPI/NCCL, but for llama.cpp RPC the same physical link is still valuable as a low-latency, high-bandwidth TCP path.

NVIDIA's `connect-two-sparks` playbook confirms that a correctly seated one-cable setup commonly shows `enp1s0f1np1` / `enP2p1s0f1np1` as `Up`. It then requires netplan or manual IP assignment on the active `enp1...` interface, followed by passwordless SSH between the two Spark nodes over the CX-7 addresses.

## Setup Attempt Results

Setup actions attempted from this session:

1. Confirmed both likely Sparks are online on Tailnet with `tailscale status`.
2. Confirmed Tailscale ping to `phase-f-dgx-spark` and `spark-b4ec`.
3. SSH'd into `spark-b4ec` and inspected `ibdev2netdev`, `ip -br addr`, and sudo availability.
4. Confirmed `spark-b4ec` has `enp1s0f1np1` link `UP` but no IPv4 address.
5. Tried SSH to `phase-f-dgx-spark` by hostname, Tailnet hostname, Tailnet IP, and from `spark-b4ec`.
6. Tried Tailscale SSH to `phase-f-dgx-spark`.

Original blocking results:

- `spark-b4ec`: `sudo -n true` returns `sudo: a password is required`.
- `phase-f-dgx-spark`: host-key verification fails for hostname/Tailnet hostname.
- `phase-f-dgx-spark` by IP with `phsivince` fails `Permission denied (publickey,password)`.
- Because both CX-7 IPv4 configuration and host-key repair require privileged or trust-changing actions, no network config was changed from this session.

Updated execution state:

- SSH, host-key trust, and sudo blockers have been cleared on both Sparks.
- Temporary CX-7 IPv4 addresses are configured and verified.
- A project execution spec now exists at `.orchestrator/dgx-spark-glm-cluster/SPEC.md`.
- Next durable step is NetworkManager persistence via `nmcli`, followed by `llama.cpp` CUDA/RPC bootstrap.

## Candidate Approaches

### Approach A: llama.cpp Coordinator + RPC Worker over CX-7

Build current `llama.cpp` with CUDA and RPC support on both Sparks. Run `rpc-server` on one Spark over the CX-7 IP. Run `llama-server` on the coordinator with the merged `UD-IQ1_M` GGUF file and `--rpc <worker-cx7-ip>:50052`.

Pros:

- Native fit for GGUF.
- Directly supports one model split across networked devices through llama.cpp RPC.
- Exposes a normal HTTP server that can sit behind an OpenAI-compatible adapter or llama.cpp's built-in OpenAI-compatible endpoints, depending on the current server feature set.
- The 231 GB quant is plausibly within the combined memory envelope of two GB10 systems if context and concurrency are kept conservative.

Cons:

- Two 121 GB-ish unified-memory nodes leave little headroom for OS, CUDA, graph buffers, and KV cache.
- 1M context is not realistic on two Sparks with this quant; start much smaller.
- RPC performance depends heavily on the direct CX-7 link; Tailscale/Wi-Fi/WAN paths are not appropriate for tensor traffic.
- Uncensored/abliterated model should not be exposed publicly or used in unsupervised production contexts.

Risk: Medium-high for first successful load; medium after a small-context smoke test passes.

Effort: Medium.

Blast radius: Mostly isolated to the two Sparks and this repo's bootstrap scripts.

### Approach B: Single-Spark llama.cpp with CPU/Unified-Memory Spill

Attempt to run the `UD-IQ1_M` model on one Spark with partial GPU offload and CPU/unified-memory fallback.

Pros:

- Avoids distributed RPC and CX-7 setup for initial validation.
- Simpler operational model.
- Useful as a llama.cpp build/model-format smoke test.

Cons:

- 231 GB weights alone exceed one Spark's practical memory budget.
- Likely too slow or unstable for real repo loops.
- Does not use the new QSFP cable or second Spark meaningfully.

Risk: High for usable performance.

Effort: Low-medium.

Blast radius: Low.

### Approach C: vLLM/SGLang NVFP4

Keep the prior vLLM/SGLang NVFP4 route as a fallback only if GGUF/llama.cpp fails or a different GLM-5.2 checkpoint becomes the target.

Pros:

- Stronger serving stack for conventional OpenAI-compatible inference if the right checkpoint fits.
- Ray/NCCL patterns are well documented.

Cons:

- Not the requested model artifact.
- The official NVIDIA NVFP4 checkpoint is much larger/different and tested on B200/B300, not two GB10 Sparks.
- More kernel/runtime uncertainty on GB10.

Risk: High for this user goal.

Effort: Medium-high.

Blast radius: Medium.

### Approach D: Tailscale-Only RPC

Run llama.cpp RPC over Tailnet addresses instead of configuring the QSFP/CX-7 link.

Pros:

- Easiest to try once SSH works.
- No network reconfiguration.

Cons:

- Current evidence shows `spark-b4ec` may route to peers through non-local paths.
- RPC tensor traffic over Tailscale/WAN latency will likely be unusable for a model this large.
- Can produce misleading failures that look like model/runtime problems.

Risk: High.

Effort: Low.

Blast radius: Low but likely wastes debugging time.

## Recommendation

Use Approach A as the target, with a strict setup gate before downloading/running the 231 GB model.

Immediate order:

1. Persist the verified temporary QSFP/CX-7 addresses with NetworkManager (`nmcli`) because both nodes use NetworkManager as the renderer.
2. Configure the QSFP/RoCE interface on both Sparks using static IPv4s on `enp1s0f1np1`, for example:
   - `phase-f-dgx-spark`: `192.168.100.10/24`
   - `spark-b4ec`: `192.168.100.11/24`
3. Verify `ping` and SSH over the CX-7 IPs.
4. Build identical `llama.cpp` commits on both nodes with CUDA and RPC enabled.
5. Start `rpc-server` on the worker:
   - `./build/bin/rpc-server --host 0.0.0.0 --port 50052`
6. Validate with a small GGUF model before downloading GLM.
7. Download and merge the `UD-IQ1_M` split GGUF on the coordinator:
   - `huggingface-cli download huihui-ai/Huihui-GLM-5.2-abliterated-GGUF --local-dir /models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF`
   - `llama-gguf-split --merge /models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/UD-IQ1_M/GLM-5.2-UD-IQ1_M-00001-of-00006.gguf /models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf`
8. Launch with a deliberately small context first:
   - `llama-server -m /models/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF/GLM-5.2-UD-IQ1_M.gguf --rpc 192.168.100.11:50052 -ngl 99 --ctx-size 8192 --parallel 1 --host 0.0.0.0 --port 8080`
9. Increase context only after load, first-token, and short generation are stable. Do not start anywhere near 1M context.
10. Put a stable local inference URL in front of the server and route repo loops through environment variables:
    - `OPENAI_BASE_URL=http://<coordinator-tailnet-name>:8080/v1`
    - `OPENAI_API_KEY=<local token or placeholder if server does not enforce auth>`
    - `LOCAL_INFERENCE_MODEL=huihui-glm-5.2-abliterated-ud-iq1-m`

Use the abliterated model only in controlled local research and coding loops. The model card explicitly warns that safety filtering is reduced and that outputs can be sensitive, controversial, inappropriate, or legally/ethically risky.

## Open Questions

- Which Spark should be the coordinator holding the merged 231 GB GGUF file?
- Do both Sparks have enough free disk for the download and merge workflow? The coordinator should have substantially more than 231 GB free because split files and merged output can temporarily coexist.
- What is the correct verified host key for `phase-f-dgx-spark`?
- Can the operator provide interactive sudo once so netplan can be configured?
- Should the endpoint be available only over Tailnet, or also on LAN?
- Should repo loops route directly to `llama-server`, or should this repo provide a small authenticated reverse proxy/model alias layer?

## Validation and Scoring

Rubric score: 91/100.

- Internal constraints: 18/20. Repo is small and fully mapped; remote host-key/auth state prevented complete inspection of both nodes.
- External evidence: 20/20. Target model card, Grok/X summary, llama.cpp RPC docs, and NVIDIA Spark networking docs are included.
- Candidate approaches: 19/20. Four approaches with pros/cons/risk/effort/blast radius, now aligned with GGUF.
- Recommendation strength: 19/20. Clear setup gates and a conservative first-run command.
- Source traceability: 15/20. URLs are listed below; live command outputs are summarized in this brief.

Control arm: the earlier vLLM/NVFP4 research scored lower for the corrected user intent because it targeted the wrong artifact. The updated GGUF/llama.cpp route is the better handoff.

Convergence: sufficient for project-orchestrator handoff after manual SSH/sudo blockers are cleared. Further research should be triggered only if llama.cpp cannot load this GLM DSA GGUF on current builds or if the two-node memory budget fails at small context.

## Scaling Path (3rd / 4th Node)

Verified against NVIDIA Cluster Assistant + the "Connect Three Sparks" playbook
(updated 2026-03-19). The reason to add nodes is memory to hold a higher-quality
quant, not speed. Decode stays memory-bandwidth-bound (~7 tok/s range) regardless
of node count; more nodes buy capacity/quality, not throughput.

### Topology facts

Each DGX Spark has two ConnectX-7 QSFP ports (4 logical RoCE interfaces). A single
cable joins only 2 nodes, but the second port is what enables 3 nodes cable-only.

| Nodes | Topology | Cables | Switch |
|---|---|---|---|
| 2 (current) | Direct, one port each | 1 | No |
| 3 | Ring / full mesh, both ports each | 3 | No |
| 4 | Star via managed 200G QSFP switch | 4 (node->switch) | Yes |

Current cluster uses only one of the two ports (single cable). Moving to 3 nodes
means lighting up both ports on every Spark.

### 3-node ring cabling (no switch)

Port0 = CX7 port next to the Ethernet port; Port1 = the CX7 port farther away.

- Node1 Port0 -> Node2 Port1
- Node2 Port0 -> Node3 Port1
- Node3 Port0 -> Node1 Port1

Then assign all four CX7 interfaces per node (NVIDIA `connect-three-sparks`
netplan example uses `192.168.0.0/24` ... `192.168.5.0/24` link subnets), set up
passwordless SSH across all three over the CX7 IPs, and validate with the NCCL
bandwidth test. Requires 2 additional QSFP cables (currently have 1).

### 4-node switch

Each node connects to a managed QSFP switch with enough 200 Gbps-class ports.
NVIDIA does not validate a 4-node cable-only mesh (only 2 ports per node). Requires
a switch plus 4 cables.

### Memory / quant targets (abliterated GLM-5.2)

Each Spark ~128 GB unified (~120 GB usable after OS). Quant sizes: IQ1_M 231 GB,
Q2_K ~253 GB, Q3_K_M ~343 GB.

| Config | Usable mem | Comfortable quant | Notes |
|---|---|---|---|
| 2 Sparks (now) | ~240 GB | IQ1_M (231 GB) | Tight; ~8 GB swap on load |
| 3 Sparks | ~345 GB | Q2_K (253 GB) | ~90 GB KV headroom; Q3_K_M only at tiny context |
| 4 Sparks | ~460 GB | Q3_K_M (343 GB) | ~115 GB KV headroom + long context |

### Recommendation

- Add a 3rd Spark first: cheapest upgrade (2 cables, no switch), moves off the
  marginal 1-bit quant to a comfortable Q2_K (2.5-bit) — the biggest single
  quality jump for code loops.
- Only go to 4 if Q2_K quality is still insufficient or long-context windows are
  needed, in which case target Q3_K_M and budget for a managed QSFP switch.
- Do not expect higher tok/s from more nodes; expect better output quality.

## Sources

- Grok/X post on abliterated GLM-5.2 GGUF: https://x.com/grok/status/2071814737856225410
- `huihui-ai/Huihui-GLM-5.2-abliterated-GGUF`: https://huggingface.co/huihui-ai/Huihui-GLM-5.2-abliterated-GGUF
- llama.cpp RPC README: https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md
- NVIDIA DGX Spark User Guide, "Spark Stacking": https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
- NVIDIA DGX Spark playbook, "Connect Two Sparks": https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/connect-two-sparks/README.md
- NVIDIA DGX Spark playbook, "NCCL for Two Sparks": https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nccl/README.md
- NVIDIA DGX Spark playbook, "Connect Three Sparks (ring)": https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/connect-three-sparks/README.md
- NVIDIA Sync, "Cluster Assistant for ConnectX-7 Multi-Node Clusters": https://docs.nvidia.com/sync/latest/cluster-assistant.html
