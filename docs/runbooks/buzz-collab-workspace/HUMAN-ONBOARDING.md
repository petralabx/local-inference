# Buzz human onboarding (pilot cohort)

Cohort: **Vince**, **Ricardo**, **Stephen**.

## Prerequisites

- On the PLX Tailscale tailnet (same as `lattice-prod`).
- Buzz Desktop (or equivalent client) from
  https://github.com/block/buzz/releases/latest
- Relay URL from the operator (prefer `wss://…ts.net` — see
  `EC2-COMPOSE-TAILSCALE.md`).

## Steps

1. Install Buzz Desktop for your OS.
2. Create / import your Nostr identity (backup your secret offline).
3. Send your **public** key (hex or npub) to Vince for `add-member` if the relay
   is closed.
4. In the app, set the relay to the pilot URL (or `BUZZ_RELAY_URL` before launch).
5. Join the pilot channel(s) named in `PILOT-PLAYBOOK.md`.
6. Post a short hello and confirm you can see Vince’s message (reachability OK).

## Daily habit (pilot success signal)

Before starting a long portal agent/dev run, open the Buzz channel, state intent
in 2–4 sentences, and wait for human/agent feedback.

## Troubleshooting

| Symptom | Check |
|---|---|
| Cannot connect | Tailscale status; relay `./run.sh status`; URL scheme `wss` vs `ws` |
| Connected but cannot post | Membership (`add-member`); closed-relay owner policy |
| App points at localhost | Clear/override relay URL |

## Rollback

Leave the channel; uninstall Desktop if desired. No server change required.
