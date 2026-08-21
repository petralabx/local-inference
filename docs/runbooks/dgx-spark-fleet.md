# DGX Spark Fleet — Inventory, Network, and Cluster Runbook

> **Canonical home** for the two-Spark GLM cluster plan, stable IPs, and cable-day
> checklist. Agents and operators: read this before touching DGX networking or
> LiteLLM cutover. Last verified: **2026-06-28**.

## Client contract (unchanged)

All loops and agents call the **Dell LiteLLM proxy**, never Spark backends directly:

| Field | Value |
|-------|--------|
| Base URL (preferred) | `http://100.103.33.54:4000/v1` |
| Base URL (LAN) | `http://192.168.2.12:4000/v1` |
| Primary alias | `local-primary` |
| Fast fallback | `local-fast` |
| GLM cluster (after cutover) | `local-glm52-experimental` |

Control-plane repo: `C:\Users\vince\local-inference` (this tree).

## Fleet inventory

| Node | Hostname | LAN IP | Tailscale IP | TS name | SSH user | Sync alias | DGX OS | Status |
|------|----------|--------|--------------|---------|----------|------------|--------|--------|
| Dell control plane | `VTA` | `192.168.2.12` | `100.103.33.54` | `vta` | `phsi\vince` / `vince` | — | Windows | LiteLLM `:4000`, vLLM `:8000` |
| Spark #1 | `spark-7d3d` | `192.168.2.17` | `100.111.220.1` | `phase-f-dgx-spark` | `vinnysachet` | `V_SACHET_TB` | 7.x | Online, Sync, Tailscale, `tag:dgx` |
| Spark #2 | `spark-b4ec` | `192.168.2.21` | `100.92.253.61` | `spark-b4ec` | `vinnysachet2` | `spark-b4ec` (Sync) | 7.5.0 | Online, Sync, Tailscale, `tag:dgx` |

**Bell router:** gateway `192.168.2.1`. Subnet moved from `192.168.1.x` on 2026-06-26;
do not use stale addresses (`192.168.1.93`, `192.168.137.x`, or `.local` until mDNS
catches up).

## Two networks (do not mix)

| Network | Purpose | Medium |
|---------|---------|--------|
| **Management** | Internet, SSH, Tailscale, LiteLLM API | Bell LAN / Wi‑Fi / Tailscale |
| **GPU fabric** | Spark↔Spark NCCL / tensor parallel | QSFP ConnectX-7 only |

Never route Spark internet through Dell ICS or a `Dell-Direct` link. Spark #1 needed
**delete `Dell-Direct`** and default route via `192.168.2.1` before Tailscale worked.

## Architecture target

```text
All loops/agents → Dell LiteLLM :4000 (aliases)
                      ├─ local-fast / local-primary → Dell vLLM :8000 (small models)
                      └─ local-glm52-experimental   → DGX cluster vLLM :8000 (GLM 5.2)

Management: Bell LAN + Tailscale
GPU fabric: QSFP between Sparks (NVIDIA Sync Cluster Assistant)
```

Example LiteLLM backend cutover: `litellm/config.dgx.example.yaml`.

## Completed (2026-06-28)

- [x] Spark #1 recovered on Bell LAN; Tailscale online; NVIDIA Sync connected
- [x] Spark #2 first boot completed (headless OOBE; recovery not required)
- [x] Spark #2 Tailscale installed and joined tailnet
- [x] Spark #2 added to NVIDIA Sync
- [x] Both Sparks reach internet (`curl https://google.com` → 301)
- [x] No `Dell-Direct` / `192.168.137.x` on Spark #2

## Blocked until hardware arrives

- [ ] **Cat6a** — wire both Sparks to Bell LAN (`enP7s7`; Spark #2 currently on Wi‑Fi `wlP9s9`)
- [ ] **QSFP DAC** (0.4m, 200G QSFP56 / Spark-validated) — direct Spark↔Spark
- [ ] **NVIDIA Sync → Cluster Assistant** — 2-node direct topology
- [ ] **NCCL smoke test** on ConnectX-7 fabric
- [ ] **Dual-Spark vLLM** — smaller model first, then GLM 5.2 4-bit (TP=2 or PP=2)
- [ ] **LiteLLM cutover** — point `local-glm52-experimental` at cluster `:8000`
- [ ] **DHCP reservations** on Bell for `.17` and `.18` (recommended)

## Cable-day runbook (ordered)

### 1. Ethernet (Bell LAN)

1. Plug **both Sparks** into Bell router LAN ports.
2. On each Spark (SSH): confirm one default route via `192.168.2.1`; delete any
   `Dell-Direct` profile if present.
3. Optional: set DHCP reservations on Bell for fixed LAN IPs.

### 2. QSFP fabric (Spark ↔ Spark)

1. Power off both Sparks (or hot-unplug QSFP only when powered down).
2. Insert **same QSFP port** on each unit (direct DAC, no switch for 2-node).
3. Power on; confirm both still on Bell LAN + Sync.

### 3. Cluster Assistant

1. NVIDIA Sync → **Cluster Assistant** → 2-node direct connection.
2. Complete ConnectX-7 netplan + inter-node SSH setup.
3. Run NCCL smoke test before loading GLM.

### 4. Inference + proxy

1. Deploy vLLM (or TRT-LLM) on the 2-node cluster at `:8000`.
2. Prove a **small** dual-Spark model, then GLM 5.2 4-bit.
3. Edit `litellm/config.yaml` (see `config.dgx.example.yaml`); restart proxy.
4. Smoke: `./scripts/smoke_proxy.sh` from Dell.

## Quick SSH reference (from Dell PowerShell)

Primary path (both Sparks tagged `tag:dgx`, Tailscale SSH on — ACL
`autogroup:admin` → `tag:dgx` as `vinnysachet` / `vinnysachet2`):

```powershell
tailscale ssh vinnysachet@phase-f-dgx-spark
tailscale ssh vinnysachet2@spark-b4ec
```

Break-glass (NVIDIA Sync / LAN / fleet keys):

```powershell
# Sync ssh_config (nvsync.key). Spark #1 uses LAN; prefer LAN for Spark #2 too.
ssh -F "$env:LOCALAPPDATA\NVIDIA Corporation\Sync\config\ssh_config" V_SACHET_TB
ssh -o IdentitiesOnly=yes -i "$env:LOCALAPPDATA\NVIDIA Corporation\Sync\config\nvsync.key" vinnysachet2@192.168.2.21

# Hermes / operator fleet keys (also installed on vmc-prod + swarm-prod)
ssh -i $env:USERPROFILE\.ssh\hermes_fleet_ed25519 -o IdentitiesOnly=yes vinnysachet@100.111.220.1
ssh -i $env:USERPROFILE\.ssh\hermes_fleet_ed25519 -o IdentitiesOnly=yes vinnysachet2@100.92.253.61
```

NVIDIA Sync: prefer **LAN or Tailscale `100.x` IP** over `.ts.net` MagicDNS.
Operator-access fabric: `agentic-swarm` `config/operator-hosts.yaml`
(`dgx-spark`, `dgx-spark-2`, `hermes_identity`).

## Pitfalls (learned)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Sync can't connect | Stale IP / offline Spark | Use current LAN or TS IP; re-add device in Sync |
| `tailnet policy does not permit you to SSH as user …` | Tailscale SSH on + ACL missing Linux user | Access controls → Tailscale SSH: `tag:dgx` users must include `vinnysachet` and `vinnysachet2` |
| Spark #2 LAN wrong | Old reservation `.18` | Use `192.168.2.21` (observed 2026-08-12) |
| `/welcome/update` refused | OOBE web server shut down after updates | Use SSH + Sync, not browser setup URL |
| Tailscale offline on Spark | Default route via `192.168.137.1` | Delete `Dell-Direct`; use Bell LAN only |
| `spark-*.local` wrong IP | mDNS stale after router swap | Use `192.168.2.x` or Tailscale IP |
| Sync IP not editable | Sync limitation | Delete device and re-add with new IP |
| `tailscale: command not found` | Not pre-installed on fresh Spark | Official apt install (see NVIDIA Spark Tailscale guide) |
| Headless OOBE password fails | Account not committed after long update | Monitor+keyboard or USB recovery |

## Scale-out notes (4 Sparks, +2 months)

- **GLM cluster peers:** more DGX Spark / Dell Pro Max GB10 (ConnectX-7), not Ryzen minis.
- **Ryzen minis:** orchestration, LiteLLM redundancy, small-model workers — not NCCL peers.
- **4-node fabric:** MikroTik CRS812 DDQ + 200G DACs + 400G→2×200G breakout (not on Amazon.ca;
  order from MikroTik Canada).
- **10G LAN switch (optional):** QNAP QSW-M3212R-8S4T for clean Dell + Spark wiring.

## Related repos / docs

| Repo | Doc | Scope |
|------|-----|--------|
| `local-inference` | This file | Inference proxy, cluster cutover, cable day |
| `local-inference` | `README.md` | Client contract, boot durability |
| `local-inference` | `litellm/config.dgx.example.yaml` | Post-cluster LiteLLM config |
| `local-inference` | `docs/runbooks/spark-b-qwen36-nvfp4-bakeoff.md` | Spark B abliterated NVFP4+MTP bake-off on `:18091` (do not cut over `local-driver`) |
| `agentic-swarm` | `docs/runbooks/dgx-spark-worker-bringup.md` | Spark #1 compute-fabric worker (`vinnysachet`) |
| `agentic-swarm` | `docs/runbooks/local-inference-tradingbox-bridge.md` | TRADINGBOX → Dell proxy bridge |
| `agentic-swarm` | `config/operator-hosts.yaml` | Operator mesh (`dgx-spark`, `dgx-spark-2`, EC2, Dell) |

Spark #2 (`vinnysachet2`) is in `operator-hosts.yaml` as `dgx-spark-2` but not yet
in `trading-workers.yaml` as an active compute worker.

## Spark B NVFP4 bake-off (not a cutover)

Abliterated Qwen3.6-35B-A3B NVFP4+MTP may be served on Spark B **side port
`:18091`** next to live llama.cpp GGUF on `:18090`. Optional proxy alias
`local-driver-nvfp4` lives in `litellm/config.spark-b-nvfp4.example.yaml` only.
Do not replace `local-driver`. Do not point `local-primary` at Spark B.
Runbook: `docs/runbooks/spark-b-qwen36-nvfp4-bakeoff.md`.

## Session handoff checklist

When resuming work in a new Cursor/agent session:

1. Read this file.
2. From Dell: `ssh` both Sparks (table above) + `curl -s http://127.0.0.1:4000/v1/models` (proxy).
3. Confirm Tailscale: `tailscale status` on Dell shows both Sparks **online**.
4. If cables arrived → start at **Cable-day runbook** §1.

**VMC todo:** `todo-51198375` — *DGX Spark QSFP cable day — 2-node cluster + GLM cutover*
