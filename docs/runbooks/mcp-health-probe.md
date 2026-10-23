# MCP health probe (scheduled)

`scripts/mcp_health_probe.py` runs the [protocol smoke](mcp-target-smoke.md)
checks (initialize, discovery, self-check) against every **enabled** server in
`.mcp.json`, records last-good / last-error state, and alerts on changes only.

## Source root and path overrides

Both the smoke harness (#56) and health probe (#57) accept `--root PATH`,
`--config PATH` and `--settings PATH`. Resolution happens at invocation:

1. CLI paths win. `--root` supplies both source defaults and suppresses environment
   source paths; `--config` / `--settings` still override those defaults.
2. `LOCAL_INFERENCE_ROOT` selects a checkout. `MCP_CONFIG_PATH` and
   `MCP_SETTINGS_PATH` override its default source files independently.
3. Without a root override, try the script's own checkout, then
   `git rev-parse --show-toplevel` from the current directory (including nested directories).

A checkout must contain `.mcp.json` and `config/execution-primitives.local.yaml`
with the identity line `repo: petralabx/local-inference`. This also supports
repository copies without Git metadata. Defaults remain `.mcp.json` and
`.claude/settings.json` under that checkout. A standalone explicit config file
is supported; provide both source paths when no checkout is available.
Missing default or CLI settings files remain optional (no expected-tool list),
as in the original harness; an environment settings override must exist.
Invalid root/config/environment-settings overrides fail with exit 2, even if
a discoverable checkout exists. Diagnostics list tried paths and override names;
they do not inspect credentials. State is refused inside either the script's
checkout or the selected checkout.

```bash
LOCAL_INFERENCE_ROOT=/srv/local-inference python3 scripts/mcp_health_probe.py --status
python3 scripts/smoke_mcp_targets.py --root /srv/local-inference --help
```

## Enable / disable a target

Enabled by default. To stop probing one, add to its `.mcp.json` entry:

```json
"smoke": { "enabled": false }
```

Disabled targets are not probed, never alert, and show as `disabled` in the
status view. (The `smoke_mcp_targets.py` harness itself ignores this flag.)

## State file

Default: `$MCP_HEALTH_STATE`, else `$XDG_STATE_HOME/local-inference/mcp-health.json`
(`~/.local/state/...`), on Windows `%LOCALAPPDATA%\local-inference\mcp-health.json`.
`--state PATH` overrides. A path inside the repo is refused. Written atomically
(temp file + rename). A corrupt file is moved to `<name>.corrupt` and probing
starts fresh with a warning.

Per target: `status` (`ok` / `failing` / `skipped` / `unknown`), `last_checked_at`,
`last_ok_at`, `last_error_at`, `last_error_category` (`STARTUP`, `PROTOCOL`,
`DISCOVERY`, `AUTH`), `last_error_detail` (redacted, max 500 chars),
`consecutive_failures`, plus alert bookkeeping (`alert_category`, `last_alert_at`).
Credential values are never written. A `SKIPPED (no credential)` probe sets
`skipped` and does not touch last-ok/last-error.

## Alerts

One JSON line on stdout per alert: `{"target","at","event","category","detail"}`.
Events: `failing` (ok to failing), `category_changed`, `recovered`, and
`still_failing` (same failure re-alerted after `--realert-after HOURS`,
default 6). Repeats inside the window are silent. If
`MCP_HEALTH_WEBHOOK_URL` is set, each alert is also POSTed there as JSON (the URL
is a secret; it is never logged). A failed delivery is not counted as sent, so it
retries on the next run.

## Reading status

```bash
.venv/bin/python scripts/mcp_health_probe.py --status   # table, no probing
.venv/bin/python scripts/mcp_health_probe.py --json     # same data as JSON
```

Both exit 1 if any enabled target is currently failing (`--require-all` also
counts skipped / never-probed). A plain run probes, updates state, prints the
table to stderr and exits 1 on any failing target. Exit 2 = config/usage error.

## Install (operator step; nothing here is auto-installed)

Linux: copy `deploy/mcp-health/mcp-health-probe.{service,timer}` to
`/etc/systemd/system/`, set `User=`, create
`/etc/local-inference/mcp-health.env` (mode 0600) with `MC_MCP_API_KEY=...` and
optionally `MCP_HEALTH_WEBHOOK_URL=...`, then
`systemctl daemon-reload && systemctl enable --now mcp-health-probe.timer`
(every 15 min). The unit defaults `LOCAL_INFERENCE_ROOT` to `/opt/local-inference`;
set `LOCAL_INFERENCE_ROOT=/srv/local-inference` in the environment file (or a
systemd drop-in) to override it. The interpreter, script and working directory
all follow that root, including paths with spaces. `MCP_CONFIG_PATH` and
`MCP_SETTINGS_PATH` may also be set in that file. Ensure the service user can
read the checkout and its venv; `ProtectHome=true` prevents roots under home
directories unless an operator adjusts the sandbox. After updating an installed
unit, run `systemctl daemon-reload`; subsequent timer runs use the new settings.
Check with `systemctl list-timers` and `--status`.

Windows (Dell): set `MC_MCP_API_KEY` as a user environment variable, run
`powershell -File scripts\register_mcp_health_probe.ps1` to preview, then add
`-Install` to register (default every 15 min; `-IntervalMinutes` to change).
`-RepoRoot` wins over `LOCAL_INFERENCE_ROOT`, then the registrar's own checkout.
The default Python follows that root; `-Python` overrides it. The task passes
`--root` explicitly so the selected root persists across scheduled runs.
To change the root after registration, preview and register again. To persist
custom source files, add `--config` / `--settings` to the registered task arguments
(`--root` suppresses source environment defaults).

Uninstall: `systemctl disable --now mcp-health-probe.timer` and delete the units,
or `Unregister-ScheduledTask LocalInference-McpHealthProbe`. State file can be deleted.

## Tests

`python -m pytest tests/test_mcp_health_probe.py` (offline: fake MCP server,
fake clock, fake alert sink; no webhook is ever called).

## Startup records and timeouts

The probe inherits per-phase startup records (`MCP_STARTUP_LOG`) and phase
timeouts (`MCP_STARTUP_TIMEOUT_*`) from the harness; see
[mcp-startup-logs.md](mcp-startup-logs.md).
