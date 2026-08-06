---
project: buzz-collab-workspace
created: 2026-08-06T10:22:02Z
updated: 2026-08-06T13:57:55Z
status: approved
approved_by: Vince Alton
approved_at: 2026-08-06T13:17:00Z
discovery_candidate: sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e
research: .orchestrator/buzz-collab-workspace/RESEARCH.md
mode: research+plan
execution_authorized: true
execution_authorized_by: Vince Alton
execution_authorized_at: 2026-08-06T13:57:55Z
execution_auth_provenance: >-
  Cloud Agent chat https://cursor.com/agents/bc-4cd9576b-709b-4353-979f-cbd925788485
  verbatim "authorize execution"
pilot_host:
  provider: aws-ec2
  region: us-east-1
  instance_id: i-03b18532cda3c6be6
  instance_name: lattice-prod
  instance_type: t3a.large
  ami: ubuntu-noble-24.04-amd64
  sizing_verdict: adequate-for-pilot
  notes: >-
    2 vCPU / 8 GiB meets upstream guidance (≥2 vCPU / ≥4 GiB). Co-tenant with
    existing Lattice workloads — confirm free RAM/disk and Docker Compose ≥2.24.4
    before install. Prefer Tailscale wss over public IPv4 for the pilot cohort.
model_plan:
  planner: claude-opus-5-thinking-high
  builder: gpt-5.6-sol-xhigh
  mechanical: composer-2.5-fast
  critic: cursor-grok-4.5-high
  notes: >-
    Vince-confirmed 2026-08-06. Critic requested as Grok 4.5 extra-high; catalog
    has no cursor-grok-4.5-xhigh — frozen to highest available Grok
    (cursor-grok-4.5-high).
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

**Pilot host (locked 2026-08-06):** reuse existing EC2 `i-03b18532cda3c6be6`
(`lattice-prod`, `t3a.large`, Ubuntu 24.04, `us-east-1`). Sizing is adequate for
a 3-person Buzz stack (relay + Postgres + Redis + MinIO). Co-tenancy with
Lattice must be checked at execute time (free memory/disk, port conflicts).

## Success Criteria

- [x] SPEC validates (`spec-validate.sh` exit 0) and is human-approved
      (`status: approved` + `approved_by` / `approved_at`).
- [ ] Runbooks cover: EC2+Compose+Tailscale stand-up **on the locked host**,
      key/secret handling, human onboarding (3), Hermes + Cursor agent membership
      under the L5 fence, and a pilot channel orbiting a named portal MC task.
- [ ] L5 fence is explicit in policy: allowlisted portal paths only; no
      live/customer systems; no staging RDS credentials in Buzz agent env.
- [ ] COS Seal / Portal Agent Registry bridge is documented as **out of v1** and
      named as the #1 post-pilot adapter.
- [ ] Evidence-pack template exists for the Vince+Ricardo success verdict
      (room works + one portal project completed via Buzz).
- [x] `execution_authorized: true` recorded 2026-08-06T13:57:55Z by Vince Alton
      (Cloud Agent chat provenance).

## Scope

- In:
  - Docs/runbooks and orchestrator artifacts in `petralabx/local-inference`
  - Pilot topology: **existing** EC2 `i-03b18532cda3c6be6` + `block/buzz`
    `deploy/compose/` + Tailscale `wss` (no new instance required for pilot)
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
  - Provisioning a *new* EC2 for the pilot (reuse locked host unless co-tenancy
    fails the preflight)
  - Skipping the P1 co-tenancy preflight on `lattice-prod`

## Phases

### P1 — EC2 Compose Tailscale runbook
- deliverables: Operator runbook targeting locked host `i-03b18532cda3c6be6`
  (`lattice-prod`, `t3a.large`): co-tenancy preflight (free RAM ≥4 GiB preferred,
  free disk ≥20 GiB, Docker Compose ≥ 2.24.4, port map vs Lattice), deploy Buzz
  via upstream `deploy/compose/` (`./run.sh`), Tailscale join + `wss` (prefer
  `*.ts.net` / `tailscale serve` over raw public IPv4), pin `ghcr.io/block/buzz`
  image tag, liveness check, backup-hint checklist. Dell explicitly out of scope
  as relay. If preflight fails, document abort → dedicated instance path.
- depends_on: []
- owns: ["docs/runbooks/buzz-collab-workspace/**", ".orchestrator/buzz-collab-workspace/P1/**"]
- forbidden: ["litellm/**", ".github/workflows/**"]
- acceptance: `test -f docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md && rg -q "i-03b18532cda3c6be6" docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md && rg -q "deploy/compose" docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md && rg -q "Tailscale" docs/runbooks/buzz-collab-workspace/EC2-COMPOSE-TAILSCALE.md`
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
  requires reachability checklist; rollback = stop Compose stack on the host;
  no portal data touched.
- **Co-tenancy with Lattice on `lattice-prod`** → Buzz stack contends for RAM/
  CPU/ports/disk → P1 preflight aborts to a dedicated instance if headroom fails;
  rollback = `./run.sh stop` / remove Buzz compose project only.
- Agent headless auto-allow expands blast radius → P2/P4 encode L5 allowlist and
  forbid staging RDS / live-customer creds; rollback = remove agent memberships /
  revoke keys.
- Image `main` drift → P1 pins sha/tag; rollback = redeploy prior pin.
- Public IPv4 exposure without Tailscale/`wss` hygiene → prefer Tailscale path in
  P1; do not rely on open `ws://` to the public address for the cohort.
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
- note: SPEC approved and `execution_authorized: true` as of 2026-08-06T13:57:55Z
  (Vince). Phase runners / docs execution may proceed.
