# Local Inference Control Plane

PLX platform repo for local LLM inference runtime and tooling: the Dell Tower
control plane (LiteLLM proxy + vLLM backend) and the two-node DGX Spark GLM
cluster.

- MC registry: `local-inference`
- Canonical GitHub: `Petra-Lab-X/local-inference` (promotion target)
- Dev repo: `taylorvalton/local-inference` (working copy — see AGENTS.md for the dev→promote workflow)

## Contract

All loops and agents should call the proxy, not the direct backend:

- Base URL (durable, survives ISP/router changes): `http://100.103.33.54:4000/v1` (Dell Tailscale IP)
- Base URL (LAN — verify after any network change): `http://192.168.2.12:4000/v1`
- Base URL (on the Dell itself): `http://127.0.0.1:4000/v1`
- Model alias: `local-primary`
- Fallback alias: `local-fast`
- DGX GLM alias: `local-glm52` (two-node DGX Spark cluster, live since 2026-07-02)
- DGX smoke alias: `local-dgx-smoke` (small-model RPC path check)

Prefer the Tailscale address for cross-machine clients: it is the tailnet
identity and does NOT change when the local subnet/DHCP lease changes. The LAN
IP can move when the router changes — it moved from `192.168.1.96` to
`192.168.2.12` after the 2026-06-26 ISP/router swap (new subnet). Set a DHCP
reservation for the Dell on the new router to pin `192.168.2.12`, and re-verify
after any future network change.

The backend can move from Dell `:8000` to DGX head `:8000` by editing
`litellm/config.yaml`; client code should not change.

## Verified status (2026-06-26, Dell)

Live and smoke-passing against `Qwen/Qwen3-32B-AWQ` on the Dell:

- `/v1/models` via proxy — OK (exposes the three aliases)
- chat completion via `local-primary` — OK
- JSON-object structured output (`response_format`) — OK
- **tool / function calling** — requires the backend to run with
  `--enable-auto-tool-choice --tool-call-parser hermes` (now baked into the
  start scripts). The first running container was launched without these, so
  tool calls returned HTTP 400 until the backend is restarted from the script.

The master key is read from the environment (`LOCAL_LITELLM_MASTER_KEY` in
`.env.local`, gitignored) — never hardcoded in `litellm/config.yaml`.

## Current Dell facts

- Hostname: `VTA`
- LAN IP: `192.168.2.12` (was `192.168.1.96` before the 2026-06-26 router swap)
- Tailscale IP: `100.103.33.54`
- GPU: NVIDIA RTX PRO 5000 Blackwell, ~48GB VRAM
- Docker: installed (Docker Desktop + WSL2 + GPU); vLLM serving via container
- Direct backend port: `8000`
- LiteLLM proxy port: `4000`

## Today: Dell path

1. Install Docker Desktop for Windows manually if you want vLLM container serving today.
   - Enable WSL2 backend.
   - Enable NVIDIA/GPU container support.
   - Restart Git Bash/Hermes after install.
2. Re-run:

```bash
cd "$HOME/local-inference"
./scripts/check_prereqs.sh
```

3. Start the Dell-fit backend once Docker works:

```bash
./scripts/start_dell_vllm_qwen3_coder_fp8.sh
```

Fallback if the FP8 model path is flaky:

```bash
./scripts/start_dell_vllm_qwen3_32b_awq.sh
```

4. In another shell, start LiteLLM:

```bash
./scripts/start_proxy.sh
```

5. Smoke test:

```bash
./scripts/smoke_backend.sh
./scripts/smoke_proxy.sh
```

## DGX Spark fleet (canonical runbook)

Two-Spark cluster inventory, network lessons, cable-day checklist, and GLM cutover
steps live in:

**[`docs/runbooks/dgx-spark-fleet.md`](docs/runbooks/dgx-spark-fleet.md)**

Read that file at the start of any session touching DGX networking, Sync, QSFP
clustering, or the GLM lane.

## DGX GLM cluster (live since 2026-07-02)

The two-node DGX Spark cluster serves GLM-5.2 (abliterated, UD-IQ1_M GGUF) via
llama.cpp RPC over the 200G QSFP CX-7 link, managed by systemd on both nodes:

- Coordinator `spark-7d3d` (`100.111.220.1:18082`), worker `spark-b4ec` RPC on the CX-7 lane
- LiteLLM aliases: `local-glm52` (GLM) and `local-dgx-smoke` (RPC path check)
- Orchestration evidence, endpoint contract, and operations runbook:
  `.orchestrator/dgx-spark-glm-cluster/`

## Boot durability (survive a reboot)

By default the start scripts run foreground/`--rm` (good for interactive use,
gone after a reboot). To make the stack auto-start:

1. Backend as a named, auto-restarting container:
   ```bash
   ./scripts/start_dell_vllm_qwen3_32b_awq_durable.sh
   ```
   This creates container `vllm-local-primary` with `--restart=unless-stopped`.
   Docker Desktop must be set to start at login (its default).
2. Proxy as a logon Scheduled Task (run once, elevated cmd):
   ```
   scripts\install-boot-durability.cmd
   ```
   Registers task `LocalInferenceProxy` that launches `start_proxy.sh` at logon.

Verify after a reboot: `curl http://127.0.0.1:4000/v1/models`.
Remove the proxy task: `schtasks /Delete /TN "LocalInferenceProxy" /F`.

## Notes

- Do not start with GLM-5.2 on the Dell. The Dell is a proxy/control-plane/fallback host; GLM-5.2 belongs in the experimental DGX lane only if a serving-compatible quant/offload path works.
- For trading loops, favor stable structured output and queue reliability over the largest possible model.
