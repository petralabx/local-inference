#!/usr/bin/env python3
"""Minimal raw JSON-RPC stdio MCP server used by the offline smoke tests.

FAKE_MCP_MODE: ok | crash | missing_tool | auth_reject | malformed | hang
FAKE_MCP_KEY: credential the server accepts (self-check fails otherwise).
"""

import json
import os
import sys

MODE = os.environ.get("FAKE_MCP_MODE", "ok")
KEY = os.environ.get("FAKE_MCP_KEY", "")
TOOLS = ["mc_self_check", "mc_get_context"]

if MODE == "crash":
    sys.stderr.write("fake server boot failure\n")
    sys.exit(3)
if MODE == "hang":
    sys.stdin.read()
    sys.exit(0)


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def tool(name):
    return {"name": name, "description": name, "inputSchema": {"type": "object"}}


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    method, rid = req.get("method"), req.get("id")
    if rid is None:
        continue
    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": req["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "0"},
            },
        })
    elif method == "tools/list":
        if MODE == "malformed":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": "not-a-list"}})
            continue
        names = [n for n in TOOLS if not (MODE == "missing_tool" and n == "mc_get_context")]
        send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [tool(n) for n in names]}})
    elif method == "tools/call":
        if MODE == "auth_reject" or not KEY or os.environ.get("FAKE_MCP_PRESENTED") != KEY:
            text = f"invalid api key presented: {os.environ.get('FAKE_MCP_PRESENTED', '')}"
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text", "text": text}], "isError": True}})
        else:
            body = {"data": {"ok": True}, "meta": {"actor": {"repo": "petralabx/local-inference"}}}
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text", "text": json.dumps(body)}]}})
    else:
        send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "no method"}})
