# Buzz agent membership — Hermes + Cursor (pilot)

v1 agents: **Hermes** and **local Cursor** (ACP). Cursor Cloud membership is
**out of scope** for v1 (see SPEC non-goals).

Bind every agent to the **L5 allowlist** in `KEYS-AND-L5-FENCE.md`.

## Shared steps

1. Mint a dedicated Nostr keypair per agent (`buzz-admin generate-key`).
2. `add-member` the agent pubkey on the relay.
3. Add the agent to the pilot channel(s).
4. Configure author gate so the agent responds to the three humans (not the
   open internet). Prefer allowlist of Vince/Ricardo/Stephen pubkeys over
   `anyone`.

## Hermes (preferred: native gateway)

Hermes documents three Buzz paths; for a server-side identity that keeps Hermes
memory/skills/approvals, prefer the **native gateway** platform plugin:

```bash
hermes gateway setup   # choose Buzz
# Configure relay URL + dedicated agent nsec (not a human key)
```

Fallback: `buzz-acp` bridge spawning `hermes acp` over stdio — see Hermes “Buzz
Integration” docs and `block/buzz` `crates/buzz-acp/README.md`.

**Security:** headless ACP bridges may auto-allow tool use. Keep tool cwd and
credentials inside the L5 allowlist. Do not export staging RDS URLs into the
Hermes/Buzz agent environment on EC2.

## Local Cursor (ACP)

Buzz Desktop Tier-2 presets include Cursor. On a machine with the Cursor ACP
entrypoint on PATH:

- Register/select the Cursor harness in Buzz Desktop **or**
- Run `buzz-acp` with `BUZZ_ACP_AGENT_COMMAND` / `BUZZ_ACP_AGENT_ARGS` pointing at
  the Cursor ACP binary.

Same membership + allowlist rules as Hermes. Verify PATH-probed ACP works before
calling P4 done.

## Smoke

From a human client:

1. `@`mention Hermes with a harmless question (no repo writes).
2. `@`mention Cursor with a harmless question.
3. Confirm replies land in-channel and no tool ran outside the allowlist.

## Rollback

Stop gateway / `buzz-acp`; remove channel memberships; rotate agent keys if
exposed.
