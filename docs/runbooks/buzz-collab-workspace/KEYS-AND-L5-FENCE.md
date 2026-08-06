# Buzz keys, secrets, and L5 tool fence

Owner: **Vince** (infra + key backup).

## Key inventory

| Identity | Purpose | Storage |
|---|---|---|
| Relay signing key (`BUZZ_RELAY_PRIVATE_KEY`) | Membership / closed-relay ops | Sealed backup + host `.env` (mode 600) |
| Owner pubkey (`RELAY_OWNER_PUBKEY`) | Relay owner | Public OK; pair with owner secret offline |
| Human keys (Vince, Ricardo, Stephen) | Desktop clients | Each human’s Buzz identity store |
| Agent keys (Hermes, Cursor ACP bot) | Channel members | Host secret store / agent env — **not git** |

Generate agent keys (on an admin workstation, not in git):

```bash
cargo run -p buzz-admin -- generate-key
# Save nsec immediately — unrecoverable if lost
BUZZ_RELAY_PRIVATE_KEY=<relay> cargo run -p buzz-admin -- add-member --pubkey <agent-hex>
```

One keypair **per** agent. Never reuse a human key for an agent.

## Secret hygiene

- **Live (2026-08-06):** pilot secrets stored in **AWS Secrets Manager
  `buzz/pilot`** (relay key, owner, DB/Redis/MinIO/HMAC). Source them into the
  host `.env` at deploy time; keep the on-host `.env` chmod 600.
- Do **not** commit `.env`, nsecs, or bridge secrets to `local-inference` or portal.
- Rotate: mint new agent key → `add-member` → update harness env → revoke old membership.

## Auth posture (live)

- **Membership authentication enforced** — only `add-member`'d pubkeys read/publish.
- **Token authentication temporarily disabled** — upstream `block/buzz` lacks a
  token-mint path (`BUZZ_API_TOKEN`). Track upstream; re-enable when available.
  Until then, do not design agent/bridge flows that assume relay token auth.

## L5 tool fence (binding)

From approved discovery / SPEC:

1. Agents may use tools only against an **explicit allowlist** of repos/paths.
   Pilot default allowlist:
   - `plx-customer-portal` worktrees / agreed checkout paths only
2. **No** live/customer systems access from Buzz-bound agent environments.
3. **No** portal staging RDS (or other shared DB) credentials injected into the
   Buzz/agent environment on EC2.
4. EC2 relay host is not a general-purpose admin box for agents — shell/tool cwd
   constrained to the allowlist.
5. Author gates: start restrictive (`owner-only` / allowlist of the three humans’
   pubkeys); widen only with written note in
   `.orchestrator/buzz-collab-workspace/P2/`.

## Allowlist change control

Edits to the allowlist require Vince ack (infra) and, for portal paths, Ricardo
ack (portal fitness). Record in Decision Log under
`.orchestrator/buzz-collab-workspace/P2/allowlist.md`.

## Rollback

- Remove agent channel memberships; stop `buzz-acp` / Hermes gateway.
- Rotate compromised keys.
- `./run.sh stop` if the host must shed Buzz load.
