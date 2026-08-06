---
slug: buzz-collab-workspace
created: 2026-08-06T08:55:00Z
updated: 2026-08-06T09:33:00Z
status: interviewing
mode: research+plan+execute
lens_cursor: L6
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
| L2 | Users and jobs | yes | answered | 2026-08-06T09:20:00Z |
| L3 | Current reality | yes | prefilled | 2026-08-06T08:55:00Z |
| L4 | Constraints | yes | answered | 2026-08-06T09:26:00Z |
| L5 | Blast radius | yes | answered | 2026-08-06T09:33:00Z |
| L6 | Success evidence | yes | asked | — |
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

### L2 — Users and jobs

**Pilot cohort (locked):** Vince + Ricardo + Stephen (option 2). Each brings their
primary agent into the room so cross-human and cross-agent feedback is real —
not a solo spike.

**Job to be done:** before a long portal-related agent/dev run starts, the three
humans (and their agents) can review intent, constraints, and risks in a shared
Buzz channel and give immediate feedback.

**Pilot orbit (locked):** work is **plx-customer-portal**-centric, with **Mission
Control** as the project-management SoR (tasks, checkout, compliance). Buzz is
the collaboration room around that work — it does not replace MC.

**Access requirement:** Ricardo and Stephen must reach the Buzz relay from their
own machines. Resolved by L4: EC2 relay + Tailscale/hostname access (not
Dell-as-relay).

### L4 — Constraints

**Hosting (locked after reopen):**
- **Pilot and steady-state shape:** dedicated **EC2 + Compose** on the Tailscale
  net (or with a small TLS front). Same topology from day one — no Dell-as-relay
  hop, no mid-pilot migration.
- **Dell role:** agent worker only (Hermes / local models / existing bridges) —
  not the shared Buzz relay.
- Colleagues (Ricardo, Stephen) reach the relay via Tailscale membership and/or a
  stable hostname; relay uptime is independent of Vince's workstation.

**Still binding:**
- Self-hosted only (Block buzz.xyz out).
- Dedicated Buzz volumes (own Postgres/Redis/object store) — never portal staging
  RDS.
- Hermes + Cursor first-class; Portal Agent Registry / COS Seal = adapter work.
- Pilot orbit = plx-customer-portal + Mission Control as PM SoR (from L2).
- Pilot cohort = Vince + Ricardo + Stephen (from L2).

**Still open (assumptions, not blockers for this lens):**
- Exact COS Seal artifact — resolve at L7.
- EC2 size / region / who operates backups — defer to L6 graduation + L11 ops,
  with a small pilot instance acceptable to start.

### L5 — Blast radius

**Fence (locked): #2 — scoped agent tools.**

Humans stay in the loop; the room is collaborative. What changes vs solo
Cursor/Hermes is *who can @mention an agent* (any channel member) and *where
tools may run*. For the pilot:

- Agents may use tools only against **explicit allowlisted** repos/paths
  (starting with plx-customer-portal worktrees / agreed paths).
- **No** live/customer systems access from Buzz-bound agent environments.
- **No** portal staging RDS (or other shared DB) credentials injected into the
  Buzz/agent environment on EC2.
- Agent shell/tool host is constrained to the allowlist; EC2 relay host is not a
  general-purpose admin box for agents.
- Reversible: remove agent memberships / tear down the EC2 stack; Nostr audit
  trail remains for review.

Risk framing recorded for the cohort: shared trigger surface + headless
auto-allow on some ACP bridges — mitigated by allowlist, not by assuming only
Vince will ever prompt the agent.

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

- Pilot and steady-state Buzz relay run on dedicated EC2 + Compose (own
  Postgres/Redis/object-store volumes) — never portal staging RDS; Dell is agent
  worker only. Owner: Vince. Locked at L4 (2026-08-06T09:26Z).
- "COS Seal" names a concrete Portal/swarm workflow Vince wants wired into Buzz.
  Exact artifact path/owner still unknown in-repo. Owner: Vince. Resolve at L7
  (Non-Goals) — include as adapter target or explicitly exclude from v1.
- EC2 sizing / region / backup owner deferred until L6 graduation criteria and
  L11 ops. Owner: Vince. Small pilot instance is acceptable to start.
- Ricardo + Stephen will get Tailscale (and/or hostname) access to the EC2 relay
  before pilot day. Owner: Vince.
- Pilot agent tool allowlist starts at plx-customer-portal (exact paths TBD at
  plan time). Owner: Vince. Confirmed intent at L5.

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
  speed and clean ops boundary for steady-state.
- 2026-08-06 — L2 locked: cohort = Vince + Ricardo + Stephen; orbit =
  plx-customer-portal with Mission Control as PM SoR. New access requirement:
  colleagues must reach the relay from their machines.
- 2026-08-06 — **Reopened L4 pilot host** because Dell-local contradicts the L2
  cohort unless Ricardo + Stephen are on the Tailscale tailnet (or a public TLS
  front exists). Dell asleep = Buzz down for all three.
- 2026-08-06 — **L4 re-locked: EC2 + Compose for pilot** (same shape as
  steady-state). Dell stays agent worker only. Rationale: agent recommendation
  accepted by Vince; multi-human reachability and uptime outweigh Dell speed;
  avoids a mid-pilot migration.
- 2026-08-06 — L5 locked to fence #2 (scoped agent tools): allowlisted
  repos/paths only; no prod; no staging RDS creds in Buzz agent env. Rationale:
  keeps shared @mention trigger surface without full teammate network parity.

## Handoff

Not yet handed off. Discovery is at Stage 1 (adaptive interview), `lens_cursor:
L6` (Success evidence). Target mode is provisional (`research+plan+execute`)
pending the Stage 3 human decision; the Stage 4 collaborative review gate and,
for execute mode, the separate `project-orchestrator` Stage 2 execution
authorization are both still outstanding. No candidate digest exists yet.
