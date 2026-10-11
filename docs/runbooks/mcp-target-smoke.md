# MCP target protocol smoke

`scripts/smoke_mcp_targets.py` exercises every server in `.mcp.json` with the
official MCP SDK client: spawn/connect, `initialize`, `list_tools` (checked
against the expected tool set), then the authenticated self-check
(`mc_self_check`). Expected tools for a server are the
`mcp__<server>__*` entries in `.claude/settings.json` `permissions.allow|ask`;
a server may override with `"smoke": {"expectedTools": [...], "selfCheckTool": "..."}`
in `.mcp.json`.

## Failure categories (exit 1)

| Category | Meaning |
|----------|---------|
| `STARTUP` | process won't spawn or exits early, endpoint unreachable/non-auth HTTP error, no initialize reply before `--timeout` |
| `PROTOCOL` | reply is not valid MCP (schema/JSON errors, JSON-RPC errors, empty self-check) |
| `DISCOVERY` | `list_tools` succeeded but expected tools are missing |
| `AUTH` | HTTP 401/403, self-check returns an error or `ok=false`, or actor repo differs from `x-mc-repo` |

A target whose `${VAR}` credential is unset reports `SKIPPED (no credential)`,
which is **not** a pass; `--require-all` makes it a failure. Exit 2 = bad
config/usage. Credentials are read from the environment only and are redacted
from all output.

## Offline tests (CI)

```bash
python -m unittest tests.test_smoke_mcp_targets -v   # or: pytest tests/test_smoke_mcp_targets.py
```

Uses a fake stdio server (`tests/fixtures/fake_mcp_server.py`) and a loopback
HTTP stub; no network or secrets. CI runs these via the normal unit-test step.

## Live run (operator, manual; not in CI)

```bash
bash scripts/setup_linux_venv.sh
export MC_MCP_API_KEY=...            # from the fleet secret store; never commit
export MC_OPERATOR_EMAIL=cos@petrasoap.com   # optional, matches .mcp.json default
.venv/bin/python scripts/smoke_mcp_targets.py --require-all
```

Use `--target PLX-MC-Hub` to limit scope and `--timeout N` to adjust (default 30s).
