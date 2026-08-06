---
slug: buzz-collab-workspace
created: 2026-08-06T08:55:00Z
updated: 2026-08-06T09:15:00Z
status: interviewing
mode: research+plan+execute
lens_cursor: L2
---

# Discovery — Buzz Collaboration Workspace (humans + agents)

## Mission

Vince wants to try out [Buzz](https://github.com/block/buzz) (or this class of
functionality) so that colleagues **and** their agents (Cursor Cloud, Cursor,
Claude, goose, Codex, etc.) can collaborate more easily across all PLX dev
projects — the customer portal, Mission Control, local-inference, and the rest —
in one shared, self-ownable workspace where humans and agents are first-class
members with their own identities and a single audit trail.

## Lenses

| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1 | Outcome | yes | answered | 2026-08-06T09:10:00Z |
| L2 | Users and jobs | yes | asked | — |
| L3 | Current reality | yes | prefilled | 2026-08-06T08:55:00Z |
| L4 | Constraints | yes | answered | 2026-08-06T09:15:00Z |
| L5 | Blast radius | yes | open | — |
| L6 | Success evidence | yes | open | — |
| L7 | Non-goals | yes | open | — |
| L8 | Stakeholders | yes | open | — |
| L9 | Alternatives | no | open | — |
| L10 | Timing | no | open | — |
| L11 | Operations | no | open | — |
| L12 | Taste | no | open | — |

## Answers

### L1 — Outcome

Target shape is **#3 — team-wide substrate**, contingent on being able to
leverage Cursor and Hermes (Vince's heaviest agent tools) and to pipe in Portal
Agents / the Agent Registry (`agentic-swarm/config/agents.yaml`) and workflows
(COS Seal).

**What "we all win" looks like:** humans and their agents collaborate on PLX
projects in one room and get **immediate feedback from colleagues and their
agents before executing long dev runs**.

**Hosting:** must be **self-hosted**. Block-hosted buzz.xyz is out. Placement
deferred to L4 (Constraints) — provisional preference was "same servers as
portal staging code and DBs"; evidence contradicts that topology (see Decision
Log and Assumptions).

**Feasibility verdict (theoretical, evidence-based — not a commitment to build):**

| Surface | Verdict | Evidence |
|---|---|---|
| Hermes | **Yes, first-class today** | Hermes docs list 3 Buzz paths: Desktop managed runtime, `buzz-acp` relay bridge, and native Hermes gateway platform plugin (recommended for full Hermes: memory, skills, approvals, cron). Hermes is also a Tier-2 preset in Buzz Desktop. |
| Cursor (local/ACP) | **Yes in catalog; verify locally** | Buzz Desktop Tier-2 presets include Cursor as an ACP harness (`PRESET_HARNESSES`). Not Tier-1 (Goose/Claude/Codex/buzz-agent). Needs PATH-probed ACP binary. |
| Cursor Cloud | **Theoretically yes, not native** | Cloud agents run remotely and speak MCP/HTTP, not a local ACP stdio spawn. Practical path: a host-side `buzz-acp`/`buzz-cli` bridge the Cloud agent can reach, or Cloud agents use `buzz-cli` / webhook into the relay. Glue work, not config. |
| Portal Agent Registry / swarm | **Theoretically yes, custom bridge** | `agentic-swarm/config/agents.yaml` is LangGraph roster (COS, CFO, …), not ACP. To appear as Buzz members each identity needs a Nostr keypair + a process that speaks ACP or `buzz-cli`/webhook. YAML workflows + webhooks are the Buzz-native automation surface. Build work. |
| COS Seal workflows | **Unknown shape — confirm** | No matching artifact found in the workspace under that name. Treated as an assumption until Vince names the concrete workflow surface. |

Bottom line: **#3 is theoretically possible**. Hermes is the easy win. Cursor
local is catalog-supported. Cursor Cloud + Portal swarm/COS Seal require
adapters. That adapter work is the real scope driver for "team-wide substrate"
vs "Hermes-first pilot that grows."

### L4 — Constraints

**Hosting (locked):**
- **Pilot:** Dell / existing Hermes-bridge Tailscale host — reuse the machine that
  already runs Hermes; Buzz relay + agent bridges share that Tailscale identity.
- **Steady-state host (if pilot graduates):** dedicated EC2 (or equivalent) + Compose on
  the Tailscale net — clean ops boundary, not co-located with portal Vercel/RDS.

**Already binding from L1:**
- Self-hosted only (Block buzz.xyz out).
- Must support Hermes + Cursor as first-class participants; Portal Agent Registry
  / COS Seal are in-scope for the substrate vision but are adapter work, not
  day-one config.

**Still open (carried as assumptions, not blockers for this lens):**
- Exact COS Seal artifact/workflow path — not found in-repo; Vince to name later
  or waive into Non-Goals (L7).
- Whether Buzz's *own* Postgres/Redis/MinIO on the Dell for pilot is acceptable
  (local Docker Compose) vs. pointing at any existing non-portal store — default
  assumption: **dedicated local Compose volumes on the Dell for pilot**, migrate
  to dedicated volumes on EC2 for steady-state. Do not reuse portal staging RDS.

### L3 — Current reality

Prefilled from the workspace repos and MC context at Stage 0; correct anything
wrong.

Today collaboration between PLX colleagues and their agents is spread across
several disjoint surfaces:

- **Cursor Cloud / Cursor / Claude Code** for agent execution, each agent acting
  under a shared human account or token rather than its own identity.
- **Hermes** as a primary local coding executor (UAT agent Hermes-primary with
  Cursor Cloud failover; Hermes bridge on a Tailscale host).
- **PLX Mission Control** (`petralabx/PLX_MC`, `https://mc.plxcustomer.io`) as the
  task state source of truth, mirrored to SharePoint; agents check out tasks and
  stamp PRs via the PLX-MC MCP.
- **Portal agentic swarm** (`agentic-swarm/config/agents.yaml`) — LangGraph roster
  (COS, CFO, CRO, …) running separately from Cursor/Hermes coding agents.
- **GitHub** for code, PRs, and CI across `plx-customer-portal`,
  `local-inference`, `PLX_MC`, `skills`, `plx_secondbrain`, and others.
- **SharePoint / M365** as the canonical system of record for MC.
- **Email (the PLX operator/COS mailbox) and ad-hoc chat** for human coordination.

Pain: there is no single room where a human, an agent, the relevant repo/PR, the
task, and the decision record all live together with one identity model and one
audit trail. Agents borrow human credentials, context is scattered across tabs,
and cross-agent/cross-human handoffs are manual.

Buzz proposes to collapse this into one self-hostable Nostr relay where every
message, reaction, workflow step, review approval, and git event (NIP-34) is a
signed event in one log — humans and agents alike, each with their own keypair.

## Assumptions

- Pilot Buzz stack runs as dedicated Docker Compose on the Dell/Hermes-bridge
  host (own Postgres/Redis/MinIO volumes), not on portal staging RDS. Owner:
  Vince. Default unless overridden.
- "COS Seal" names a concrete Portal/swarm workflow Vince wants wired into Buzz.
  Exact artifact path/owner still unknown in-repo after L4. Owner: Vince. Resolve
  at L7 (Non-Goals) — include as adapter target or explicitly exclude from v1.
- Steady-state EC2 sizing / region / who operates it is deferred until pilot
  graduation criteria (L6) are set. Owner: Vince.

## Non-Goals

- To be filled at the Non-Goals lens (L7). Nothing excluded yet.
- Provisional (not yet binding): Block-hosted buzz.xyz is out (self-host only).

## Evidence

Read at Stage 0 / L1:

- `block/buzz` README + ARCHITECTURE.md + Block engineering blog / buzz.xyz —
  Buzz is an Apache-2.0, self-hostable, Nostr-relay-based workspace where humans
  and AI agents share rooms as first-class signed identities. Stack: Rust relay
  (`buzz-relay`, Axum WS+REST), Postgres (events + FTS), Redis (pub/sub), S3/MinIO
  (Blossom media). Agent surface via ACP harness (`buzz-acp` for Goose/Codex/
  Claude Code) and `buzz-cli` (JSON in/out for LLM tool calls). Works today:
  relay, channels, threads, DMs, canvases, media, search, audit log, desktop app
  (Tauri+React), YAML workflows, git events (NIP-34), git hosting. Being wired up:
  mobile, workflow approval gates, huddle lifecycle. Deploy options: local dev
  (`just dev`), Railway one-click relay, or `deploy/compose/` VPS bundle. Sourced
  Mission (what Buzz is) and L3 (how it maps onto PLX's current stack).
- Workspace `AGENTS.md` files + MC `mc_get_context` — PLX current stack and
  governance (MC task SoR, PLX-MC MCP, SharePoint SoR, Cursor Cloud agents,
  local-inference Dell/DGX control plane). Sourced L3 current reality and the
  self-host / secrets-handling constraints seeded as assumptions.
- Hermes Buzz integration docs
  (`hermes-agent.nousresearch.com/docs/integrations/buzz`) — three paths
  (Desktop / buzz-acp / native gateway). Sourced L1 Hermes feasibility.
- `block/buzz` `crates/buzz-acp/README.md` — Tier-1 (Goose, Claude, Codex,
  buzz-agent) vs Tier-2 presets (includes Cursor, Hermes Agent). Sourced L1
  Cursor/Hermes feasibility and "any ACP agent" BYOH path.
- Portal `docs/runbooks/uat-agent-v2.md` + `AGENTS.md` — Hermes-primary executor,
  Tailscale Hermes bridge, `agentic-swarm/config/agents.yaml` as Portal agent
  registry; portal web on Vercel, DBs on RDS. Sourced L1 Cursor Cloud / Portal
  swarm feasibility and the L4 hosting correction.

## Decision Log

- 2026-08-06 — Chose `guided-project-discovery` over a direct build because the
  request is an under-specified initiative ("try out this app or type of
  functionality") that needs scoping and stakeholder sign-off before anything is
  stood up. Rationale: wide intent-to-spec gap; a single question batch will not
  close it.
- 2026-08-06 — Home repo for the ledger is `petralabx/local-inference` because it
  is the current Cloud checkout and PLX's infra/control-plane repo, the natural
  place for self-hosted relay/infra work. Revisit if L5/L8 point the initiative
  primarily at PLX_MC or the portal.
- 2026-08-06 — `mode` set provisionally to `research+plan+execute` to reflect the
  literal "try out" intent (stand it up). This is NOT the Stage 3 mode decision;
  the human picks the binding mode after convergence.
- 2026-08-06 — L1 locked to outcome #3 (team-wide substrate) with self-host
  mandatory. Feasibility: Hermes yes; Cursor (local ACP) yes-in-catalog; Cursor
  Cloud + Portal swarm/COS Seal require adapters. Rationale: evidence from Buzz
  ACP README + Hermes Buzz docs + Portal topology; do not promise native Portal
  swarm membership without a bridge.
- 2026-08-06 — Rejected "put Buzz on the same servers as portal staging code and
  DBs" as the literal placement. Portal *code* runs on Vercel (stateless);
  staging *DBs* are RDS. Buzz needs a long-running Docker stack and must not
  share portal staging Postgres. Rationale: Truth Before Action.
- 2026-08-06 — L4 locked hosting path: **pilot = Dell/Hermes-bridge Tailscale
  host**; **steady-state = dedicated EC2 + Compose** if the pilot graduates.
  Rationale: Vince forced choice; matches existing Hermes topology for pilot
  speed and clean ops boundary for prod.

## Handoff

Not yet handed off. Discovery is at Stage 1 (adaptive interview), `lens_cursor:
L2` (Users and jobs). Target mode is provisional (`research+plan+execute`)
pending the Stage 3 human decision; the Stage 4 collaborative review gate and,
for execute mode, the separate `project-orchestrator` Stage 2 execution
authorization are both still outstanding. No candidate digest exists yet.
