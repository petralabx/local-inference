# Pointing Hermes At The Local Proxy

Target:

- Base URL: `http://127.0.0.1:4000/v1` on the Dell itself
- Tailscale URL (prefer): `http://100.103.33.54:4000/v1`
- LAN URL: `http://192.168.2.12:4000/v1` (verify after any network change)
- Model: `local-primary`

Use Hermes custom-provider config once the proxy and backend are passing smoke tests. Exact Hermes config shape can change, so prefer `hermes config edit` and verify with `hermes config` / `hermes doctor`.

Do not switch Hermes's primary model to local until `./scripts/smoke_proxy.sh` passes and a small coding/reasoning smoke succeeds. Keep frontier subscriptions available for high-blast-radius trading decisions and recovery.
