---
project: buzz-collab-workspace
created: 2026-08-06T10:22:02Z
status: draft
approved_by:
approved_at:
discovery_candidate: sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
research: .orchestrator/buzz-collab-workspace/RESEARCH.md
mode: research+plan
execution_authorized: false
model_plan:
  planner:
  builder:
  mechanical:
  critic:
budget:
  max_parallel_phases: 2
  max_attempts_per_phase: 3
  time_budget_min: 0
---

# Buzz Collaboration Workspace — Pilot Plan

## Mission

Deliver an approved, executable plan (runbooks + policy + pilot playbook) to
stand up a **self-hosted Buzz** relay on **EC2 + Compose + Tailscale** so Vince,
Ricardo, and Stephen — with Hermes and local Cursor as channel members — can
collaborate on **plx-customer-portal** work while **Mission Control** remains the
PM/task source of truth. This SPEC is the contract for *what to build*; under
mode `research+plan`, **approving this SPEC does not authorize execution**.

## Success Criteria

- [ ] SPEC validates (`spec-validate.sh` exit 0) and is human-approved
      (`status: approved` + `approved_by` / `approved_at`).
- [ ] Runbooks cover: EC2+Compose+Tailscale stand-up, key/secret handling, human
      onboarding (3), Hermes + Cursor agent membership under the L5 fence, and a
      pilot channel orbiting a named portal MC task.
- [ ] L5 fence is explicit in policy: allowlisted portal paths only; no
      live/customer systems; no staging RDS credentials in Buzz agent env.
- [ ] COS Seal / Portal Agent Registry bridge is documented as **out of v1** and
      named as the #1 post-pilot adapter.
- [ ] Evidence-pack template exists for the Vince+Ricardo success verdict
      (room works + one portal project completed via Buzz).
- [ ] `execution_authorized` remains `false` until a separate, explicit human
      authorization is recorded after SPEC approval (orchestrator Stage 2
      execution gate).

## Scope

- In:
  - Docs/runbooks and orchestrator artifacts in `petralabx/local-inference`
  - Pilot topology: EC2 + `block/buzz` `deploy/compose/` + Tailscale `wss`
  - Human cohort: Vince, Ricardo, Stephen
  - Agents in v1: Hermes + local Cursor ACP (scoped tools)
  - Pilot orbit: plx-customer-portal + Mission Control as PM SoR
- Non-goals:
  - Replacing Mission Control
  - COS Seal / Portal Agent Registry bridge (follow-on)
  - Cursor Cloud as Buzz members for v1
  - LangGraph swarm (`agents.yaml`) migration into Buzz
  - Company-wide Slack/email/GitHub cutover
  - Co-locating Buzz volumes with portal staging RDS / Vercel
  - Dell-as-relay (Dell remains agent worker only)
  - Executing AWS/EC2 provisioning or agent live cutover until
    `execution_authorized: true`

## Phases

### P1 — EC2 Compose Tailscale runbook
- deliverables: Operator runbook for provisioning a dedicated EC2 (or equivalent)
  host on the PLX Tailscale net, installing Docker Compose ≥ 2.24.4, deploying
  Buzz via upstream `deploy/compose/` (`./run.sh`), choosing `wss` via Tailscale
  HTTPS (`*.ts.net`) or PLX DNS + Caddy, pinning `ghcr.io/block/buzz` image tag,
  liveness check, backup-hint checklist. Dell explicitly out of scope as relay.
- depends_on: []
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P1/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md && rg -q "deploy/compose" docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md && rg -q "Tailscale" docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md`
- role: builder
- competitive: false

### P2 — Keys secrets and L5 allowlist policy
- deliverables: Policy + checklist for relay owner key, human/agent Nostr
  keypairs (`buzz-admin generate-key` / `add-member`), secret storage (not in
  git), and the L5 tool fence (allowlisted plx-customer-portal paths; no
  live/customer systems; no staging RDS creds in Buzz agent env). Includes
  rotation/backup owner = Vince.
- depends_on: [P1]
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P2/**"]
- forbidden: ["litellm/**", ".github/workflows/**", "**/.env*", "**/*secret*"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/KEYS-AND-L5-FENCE.md && rg -q "allowlist" docs/runbooks/buzz-collab-workspace/KEYS-AND-L5-FENCE.md && rg -q "staging RDS" docs/runbooks/buzz-collab-workspace/KEYS-AND-L5-FENCE.md`
- role: deep
- competitive: false

### P3 — Human client onboarding
- deliverables: Runbook for Vince, Ricardo, and Stephen to install Buzz Desktop
  (or equivalent client), join the self-hosted relay URL, verify Tailscale
  reachability, and join the pilot channel(s).
- depends_on: [P1]
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P3/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/HUMAN-ONBOARDING.md && rg -q "Ricardo" docs/runbooks/buzz-collab-workspace/HUMAN-ONBOARDING.md && rg -q "Stephen" docs/runbooks/buzz-collab-workspace/HUMAN-ONBOARDING.md`
- role: mechanical
- competitive: false

### P4 — Hermes and Cursor agent membership
- deliverables: Runbook to mint agent identities, register members, attach Hermes
  (prefer native gateway; fallback `buzz-acp`) and local Cursor ACP to the relay,
  set author gates appropriate for the 3-person cohort, and bind tool hosts to
  the P2 allowlist. Cursor Cloud membership explicitly deferred.
- depends_on: [P2, P3]
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P4/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/AGENT-MEMBERSHIP.md && rg -q "Hermes" docs/runbooks/buzz-collab-workspace/AGENT-MEMBERSHIP.md && rg -q "Cursor" docs/runbooks/buzz-collab-workspace/AGENT-MEMBERSHIP.md && rg -q "allowlist" docs/runbooks/buzz-collab-workspace/AGENT-MEMBERSHIP.md`
- role: builder
- competitive: false

### P5 — Pilot playbook and evidence pack
- deliverables: Pilot playbook naming how a portal MC task becomes a Buzz
  channel orbit; day-to-day "feedback before long runs" ritual; success-evidence
  pack template for Vince+Ricardo joint verdict; explicit pointer that COS Seal /
  Agent Registry bridge is the #1 post-pilot adapter (not in this SPEC's execute
  path).
- depends_on: [P3, P4]
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P5/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/PILOT-PLAYBOOK.md && test -f docs/runbooks/buzz-collab-workspace/EVIDENCE-PACK-TEMPLATE.md && rg -q "Mission Control" docs/runbooks/buzz-collab-workspace/PILOT-PLAYBOOK.md && rg -q "COS Seal" docs/runbooks/buzz-collab-workspace/PILOT-PLAYBOOK.md`
- role: mechanical
- competitive: false

## Risks & Rollback

- EC2/Tailscale misconfig leaves colleagues unable to connect → P1 acceptance
  requires reachability checklist; rollback = stop Compose / terminate instance;
  no portal data touched.
- Agent headless auto-allow expands blast radius → P2/P4 encode L5 allowlist and
  forbid staging RDS / live-customer creds; rollback = remove agent memberships /
  revoke keys.
- Image `main` drift → P1 pins sha/tag; rollback = redeploy prior pin.
- Proxy discovery approvals (Ricardo/Stephen via Vince) weaken review confidence
  → SPEC approval still requires Vince (and preferably Ricardo) to sign the SPEC
  itself; do not treat discovery proxy as SPEC approval.
- Accidental execution under `research+plan` → `execution_authorized: false` is
  mandatory until a separate written authorization; phases produce docs only
  until that gate flips.
- Rollback of merged docs-only PR → revert the integration PR; no runtime state
  in this repo.

## Worktree Plan

- base branch: `proj/buzz-collab-workspace`
- phase branches: `proj/buzz-collab-workspace/phase-<k>-<name>`
- integration branch: `proj/buzz-collab-workspace/integration`
- delivery: one integration PR into `main` for the whole project (docs/runbooks +
  `.orchestrator` evidence)
- note: do not start phase runners until SPEC is `approved` **and**
  `execution_authorized: true` (separate human gate)
