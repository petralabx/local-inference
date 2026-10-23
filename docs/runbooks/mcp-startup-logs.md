# MCP startup logs and phase timeouts

`scripts/smoke_mcp_targets.py` (and therefore the scheduled
[health probe](mcp-health-probe.md), which calls it) records one structured
line per startup phase and bounds every phase with its own timeout. Helpers
live in `scripts/mcp_startup_log.py` (stdlib only).

## Startup paths in this repo

| Path | Phases |
|------|--------|
| `scripts/smoke_mcp_targets.py` | secret_fetch (env or optional `smoke.secretFetch`), child_start (spawn/connect + `initialize`), discovery (`list_tools`), self_check (`mc_self_check`) |
| `scripts/mcp_health_probe.py` | same phases, via the harness; env knobs apply, no extra flags |
| `.mcp.json` | only `PLX-MC-Hub` (HTTP, `${MC_MCP_API_KEY}` from env); no stdio child is launched by this repo's config |
| `scripts/mc-checkout-local-inference.sh`, `scripts/compliance-checkout.mjs` | Hub HTTP checkout helpers; not MCP startup, not instrumented here |

## Log format

Off by default. Enable with `--startup-log PATH` (or `MCP_STARTUP_LOG=PATH`);
`-` or `stderr` writes to stderr, a path appends JSON lines.

```json
{"event":"mcp_startup","ts":"2026-10-11T20:01:02Z","target":"PLX-MC-Hub","phase":"discovery","duration_ms":41,"outcome":"ok","failure_class":null,"detail":""}
```

- `phase`: `secret_fetch` | `child_start` | `discovery` | `self_check`
- `outcome`: `ok` | `fail` | `timeout` | `skipped` (`skipped` = no credential)
- `failure_class` (null unless fail/timeout): `timeout` | `auth` | `spawn` |
  `protocol` | `config` | `unknown`
- `detail`: short, redacted, max 300 chars

A failed run stops at the failing phase, so later phases have no record.
Records never contain env values, headers, tokens or command lines. Exact
credential values (from `${VAR}` references and fetched secrets) and
credential-shaped text (`Bearer ...`, `token=`, `x-api-key:`, `sk-...`) are
replaced by `[REDACTED]`.

Class mapping: HTTP 401/403, rejected self-check, failed secret command -> `auth`;
cannot spawn/connect -> `spawn`; invalid MCP reply -> `protocol`; expected tools
missing, bad timeout setting or bad `secretFetch` -> `config`; any phase over
its bound -> `timeout`.

## Timeouts (seconds)

| Phase | Env var | Flag | Default |
|-------|---------|------|---------|
| secret_fetch | `MCP_STARTUP_TIMEOUT_SECRET_FETCH` | `--secret-fetch-timeout` | 10 |
| child_start | `MCP_STARTUP_TIMEOUT_CHILD_START` | `--child-start-timeout` | 20 |
| discovery | `MCP_STARTUP_TIMEOUT_DISCOVERY` | `--discovery-timeout` | 15 |
| self_check | `MCP_STARTUP_TIMEOUT_SELF_CHECK` | `--self-check-timeout` | 15 |

Flag beats env beats default; values must be > 0 (else exit 2 / `config`).
The existing `--timeout` (default 30) still caps the whole target; if it fires
the record is attributed to the phase that was running. On any timeout the
child process (or secret command's process group) is killed, the target is
reported `FAIL [STARTUP] <phase> timed out after Ns (raise ... )`, and the run
exits 1.

## Optional secret fetch command

A target may declare, in `.mcp.json`:

```json
"smoke": { "secretFetch": { "env": "MC_MCP_API_KEY", "command": ["/usr/local/bin/get-mc-key"] } }
```

Used only when `env` is not already set. Argv list, no shell; stdout (trimmed)
becomes the value; stdout/stderr/argv are never logged. Non-zero exit or empty
output -> `auth`; cannot start -> `spawn`; over bound -> `timeout`.

## Offline tests

```bash
python3 -m unittest tests.test_mcp_startup_log -v
```

Tests marked SDK skip unless the `mcp` package is installed (`requirements.txt`).
