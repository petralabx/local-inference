---
slug: buzz-collab-workspace
created: 2026-08-06T08:55:00Z
updated: 2026-08-06T08:55:00Z
status: interviewing
mode: research+plan+execute
lens_cursor: L1
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
| L1 | Outcome | yes | open | — |
| L2 | Users and jobs | yes | open | — |
| L3 | Current reality | yes | prefilled | 2026-08-06T08:55:00Z |
| L4 | Constraints | yes | open | — |
| L5 | Blast radius | yes | open | — |
| L6 | Success evidence | yes | open | — |
| L7 | Non-goals | yes | open | — |
| L8 | Stakeholders | yes | open | — |
| L9 | Alternatives | no | open | — |
| L10 | Timing | no | open | — |
| L11 | Operations | no | open | — |
| L12 | Taste | no | open | — |

## Answers

### L3 — Current reality

Prefilled from the workspace repos and MC context at Stage 0; correct anything
wrong.

Today collaboration between PLX colleagues and their agents is spread across
several disjoint surfaces:

- **Cursor Cloud / Cursor / Claude Code** for agent execution, each agent acting
  under a shared human account or token rather than its own identity.
- **PLX Mission Control** (`petralabx/PLX_MC`, `https://mc.plxcustomer.io`) as the
  task state source of truth, mirrored to SharePoint; agents check out tasks and
  stamp PRs via the PLX-MC MCP.
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

- Buzz is genuinely self-hostable on infra PLX already understands (Docker +
  Postgres + Redis + S3/MinIO; Railway one-click or a VPS/Compose bundle), so a
  trial does not require new vendor commitments. Owner: Vince. To confirm at the
  Constraints lens (L4).
- "Try out" implies at least standing up a working relay + desktop client and
  connecting one or more existing agents — not merely reading the docs. Owner:
  Vince. To confirm at the Outcome lens (L1); this is why `mode` is provisionally
  `research+plan+execute`.

## Non-Goals

- To be filled at the Non-Goals lens (L7). Nothing excluded yet.

## Evidence

Read at Stage 0:

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

## Handoff

Not yet handed off. Discovery is at Stage 1 (adaptive interview), `lens_cursor:
L1` (Outcome). Target mode is provisional (`research+plan+execute`) pending the
Stage 3 human decision; the Stage 4 collaborative review gate and, for execute
mode, the separate `project-orchestrator` Stage 2 execution authorization are
both still outstanding. No candidate digest exists yet.
