# Buzz human onboarding (pilot cohort)

Cohort: **Vince**, **Ricardo**, **Stephen**.

## Prerequisites

- Ricardo and Stephen: sign in to Tailscale with the work Microsoft account and
  be approved as ordinary Members of the **`petrasoap.com`** tailnet. Admin/IT
  admin is not required.
- Vince: use `petrasoap.com` directly or the `taylorvalton.github` profile where
  the corporate-owned `buzz` machine is shared in.
- Buzz Desktop (or equivalent client) from
  https://github.com/block/buzz/releases/latest
- **Live relay URL: `wss://buzz.tail7cdeae.ts.net`** (tailnet-only; you must be
  on the tailnet to reach it).

## Steps

1. Confirm Tailscale can see `buzz`, then open
   `https://buzz.tail7cdeae.ts.net/_readiness`; expect `{"status":"ready"}`.
2. Install Buzz Desktop for your OS.
3. Create / import your Nostr identity (backup your secret offline).
4. Send your **public** key (hex or npub) to Vince for `add-member` if the relay
   is closed.
5. In the app, set the relay to the live URL (or `BUZZ_RELAY_URL` before
   launch). Existing pilot users must use **Change community** to replace the
   former relay URL; restarting the app alone does not change its saved
   community.
6. Join the pilot channel(s) named in `PILOT-PLAYBOOK.md`.
7. Post a short hello and confirm you can see Vince’s message (reachability OK).

## Daily habit (pilot success signal)

Before starting a long portal agent/dev run, open the Buzz channel, state intent
in 2–4 sentences, and wait for human/agent feedback.

## Troubleshooting

| Symptom | Check |
|---|---|
| “User approval required” | A `petrasoap.com` Owner/Admin must approve the account; Member role is sufficient afterward |
| Cannot resolve/reach relay | `tailscale status`; confirm `buzz` is visible; open the `_readiness` URL |
| Cannot connect in Buzz | Confirm the saved community uses `wss://buzz.tail7cdeae.ts.net`; relay `./run.sh status`; URL scheme `wss` vs `ws` |
| Connected but cannot post | Membership (`add-member`); closed-relay owner policy |
| App points at localhost or former relay | Use **Change community** to save the live relay URL |

## Rollback

Leave the channel; uninstall Desktop if desired. No server change required.
