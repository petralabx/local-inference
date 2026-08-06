---
slug: buzz-collab-workspace
created: 2026-08-06T10:20:00Z
updated: 2026-08-06T10:20:00Z
status: draft
rubric_score: 88
discovery_candidate: sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
mode: research+plan
---

# RESEARCH — Buzz Collaboration Workspace (humans + agents)

## Mission and Context

Stand up a **self-hosted Buzz** relay so Vince, Ricardo, and Stephen (plus their
primary agents — Hermes and local Cursor) can collaborate on
**plx-customer-portal** work with **Mission Control** remaining the PM/task
source of truth. Win condition: the room works daily-ish, Hermes/Cursor are
@mentionable, and one real portal project is completed via Buzz; Vince + Ricardo
sign the verdict.

Binding constraints from approved discovery
(`sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e`):

- Self-hosted only; **EC2 + Compose** for pilot (same shape as steady-state).
- Dell = agent worker only (Hermes/local models), not the shared relay.
- L5 fence: scoped agent tools on allowlisted portal paths; no live/customer
  systems; no staging RDS credentials in Buzz agent env.
- COS Seal / Portal Agent Registry bridge = **follow-on after pilot** (#1
  adapter), not v1.
- Mode `research+plan`: this brief feeds an approved SPEC; it does **not**
  authorize build/execution.

## Internal Findings

- PLX agent surface today is fragmented: Cursor Cloud/Cursor, Hermes (primary
  UAT executor via Tailscale bridge), PLX-MC MCP task lifecycle, Portal Admin
  **Agent Registry** (10 live agents including `chief-of-staff` / COS Seal
  orchestrator), LangGraph `agentic-swarm/config/agents.yaml`, GitHub, SharePoint.
- Portal **web** runs on Vercel; staging DBs on RDS — neither hosts long-running
  Docker. Buzz needs its own Postgres/Redis/object store volumes.
- `petralabx/local-inference` is the infra/control-plane home (Dell LiteLLM,
  Tailscale proxy `100.103.33.54`, DGX fleet docs) — natural home for relay
  runbooks and discovery/research artifacts.
- Hermes already has **three documented Buzz integrations** (Desktop, `buzz-acp`,
  native gateway). Cursor appears as a Buzz Desktop Tier-2 ACP preset.
- COS Seal is portal-embedded (`chief-of-staff` + versioned registry + invocation
  grants). Bridging requires Nostr identities + ACP/`buzz-cli` that honors grants
  — adapter work, correctly deferred.

## External Findings

- Buzz (`block/buzz`, Apache-2.0): Nostr-relay workspace; humans and agents are
  first-class signed identities; single event log for chat, workflows, git
  (NIP-34).
- **Deploy path that matches discovery:** `deploy/compose/` (not root
  `docker-compose.yml`). `./run.sh start`; optional `BUZZ_COMPOSE_TLS=true` for
  Caddy + Let's Encrypt. Image `ghcr.io/block/buzz` (pin sha/tag for steady
  state). Requires Compose ≥ 2.24.4 for TLS overlay.
- Sizing guidance (community): ~2 vCPU, 4 GB RAM, 20–40 GB SSD for a small team
  relay.
- Tailscale-friendly patterns exist (host on tailnet; `wss://*.ts.net` via
  Tailscale HTTPS certs / `tailscale serve`; or public DNS + Caddy). Multi-human
  pilot needs reachable `wss://` without depending on Vince's workstation.
- Agent path: mint per-agent Nostr keypairs (`buzz-admin generate-key` /
  `add-member`); run `buzz-acp` (or Hermes native gateway) against the relay;
  default ACP author gate is often `owner-only` — must widen carefully for the
  3-person cohort under the L5 allowlist.
- Railway one-click relay exists but discovery rejected third-party host for the
  pilot in favor of EC2 (self-owned infra adjacent to PLX Tailscale).

## Candidate Approaches

### A — EC2 + `deploy/compose` + Tailscale (recommended)

Pros: Matches locked discovery; stable uptime for 3 humans; same topology as
steady-state; Dell stays agent worker; Tailscale keeps the relay off the public
internet if desired (`wss` via ts.net or internal hostname).

Cons: Requires AWS/EC2 + Tailscale ACLs + secret hygiene; first stand-up slower
than Railway.

Risk: Medium — ops (keys, backups, image pin) and agent tool allowlisting must be
tight on day one.

Effort: Medium (half-day to two days for a careful pilot stand-up + client
onboarding).

Blast radius: Contained to a dedicated instance + volumes; L5 fence limits agent
reach; tear-down reverses the room (audit log retained if volumes kept).

### B — Railway self-owned relay, migrate to EC2 later

Pros: Fastest remote stand-up; colleagues reach it immediately.

Cons: Data/plane on a third-party host; migration tax when moving to EC2;
conflicts with "EC2 for pilot" lock unless discovery is reopened.

Risk: Medium-high for a multi-week pilot (vendor + migration).

Effort: Low initially, Medium later (migrate).

Blast radius: Similar app risk; higher data-residency / vendor dependency.

### C — Dell Tailscale relay (rejected for this cohort)

Pros: Fastest for Vince-only spike; reuses Hermes host.

Cons: Dell sleep/reboot = room down for Ricardo/Stephen; couples Buzz to
workstation load (vLLM/Hermes).

Risk: High availability risk for a 3-person pilot.

Effort: Low.

Blast radius: Workstation compromise/load affects both inference and collab.

**Rejected** by discovery L4 re-lock; retained only as a foil.

## Recommendation

**Choose A.** Implement an EC2 (or equivalent) host on the PLX Tailscale net,
deploy Buzz via `deploy/compose/`, pin the image tag, mint owner + human + agent
keys, onboard Vince/Ricardo/Stephen desktop clients, attach Hermes (prefer native
gateway or `buzz-acp`) and local Cursor ACP under L5 allowlists, and run one
portal project with MC as PM SoR.

SPEC should phase roughly as:

1. EC2 + Compose + secrets + Tailscale/`wss` reachability smoke
2. Human client onboarding (3)
3. Hermes + Cursor agent membership (scoped tools)
4. Pilot channel orbiting a named portal MC task
5. Evidence pack for Vince+Ricardo success verdict

Explicitly **out of SPEC v1:** COS Seal/Agent Registry bridge, Cursor Cloud as
Buzz members, LangGraph swarm migration, MC replacement.

## Open Questions

- Exact EC2 size/region and whether Tailscale HTTPS (`*.ts.net`) or a PLX DNS
  name + Caddy is preferred for `wss://`.
- Named portal project / MC task that will be the first Buzz channel orbit.
- Hermes path for pilot: native gateway (③) vs `buzz-acp` (②) — recommend ③ if
  Hermes is already the heavy daily driver.
- Who holds the relay owner key backup (Vince as infra owner — confirm backup
  location).
- MC routing: Hub `mc_suggest_work` returned only fuzzy portal-scoped candidates;
  need a correctly scoped `petralabx/local-inference` (or infra) task before
  compliance stamping this PR.

## Sources

- Approved discovery candidate
  `.discovery/buzz-collab-workspace/candidates/sha256:b256d098…/CANDIDATE.md`
- Round-1 approval
  `.discovery/buzz-collab-workspace/review/round-1.md`
- https://github.com/block/buzz (README, ARCHITECTURE, `deploy/compose/README.md`)
- https://engineering.block.xyz/blog/run-your-own-buzz-relay
- https://hermes-agent.nousresearch.com/docs/integrations/buzz
- `block/buzz` `crates/buzz-acp/README.md` (Tier-1/Tier-2 harnesses)
- Portal Admin Agent Registry / COS Seal (Vince screenshots 2026-08-06)
- PLX `local-inference` / portal runbooks (Tailscale, Hermes bridge, Vercel/RDS topology)
