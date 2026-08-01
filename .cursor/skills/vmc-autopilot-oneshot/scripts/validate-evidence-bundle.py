#!/usr/bin/env python3
"""Validate a VMC AutoPilot Hybrid evidence bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


REQUIRED_FILES = {
    "REPORT.md",
    "artifacts.json",
    "commands.log",
    "mcp-evidence.json",
    "metrics.json",
    "ledger-snapshot.jsonl",
    "risks.md",
}

BUNDLE_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")


def fail(message: str) -> None:
    print(f"[validate-evidence-bundle] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.name} is not valid JSON: {exc}")


def require_object(value: object, path: Path) -> dict[str, object]:
    if not isinstance(value, dict):
        fail(f"{path.name} must be a JSON object")
    return value


def validate_artifacts(path: Path) -> None:
    data = require_object(load_json(path), path)
    if data.get("schema_version") != "autopilot.artifacts.v1":
        fail("artifacts.json schema_version must be autopilot.artifacts.v1")
    files = data.get("files")
    if not isinstance(files, list):
        fail("artifacts.json files must be a list")
    indexed = {
        item.get("path")
        for item in files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    missing = REQUIRED_FILES - indexed
    if missing:
        fail(f"artifacts.json missing required file entries: {sorted(missing)}")


def validate_metrics(path: Path) -> None:
    data = require_object(load_json(path), path)
    if data.get("schema_version") != "autopilot.metrics.v1":
        fail("metrics.json schema_version must be autopilot.metrics.v1")
    if data.get("gate_result") not in {"pass", "fail", "blocked"}:
        fail("metrics.json gate_result must be pass, fail, or blocked")
    if not isinstance(data.get("metrics"), dict):
        fail("metrics.json metrics must be an object")
    if not isinstance(data.get("detectors"), list):
        fail("metrics.json detectors must be a list")


def validate_mcp(path: Path) -> None:
    data = require_object(load_json(path), path)
    if data.get("schema_version") != "autopilot.mcp-evidence.v1":
        fail("mcp-evidence.json schema_version must be autopilot.mcp-evidence.v1")
    calls = data.get("calls")
    if not isinstance(calls, list):
        fail("mcp-evidence.json calls must be a list")
    for idx, call in enumerate(calls, start=1):
        if not isinstance(call, dict):
            fail(f"mcp-evidence.json call {idx} must be an object")
        if call.get("descriptor_read") is not True:
            fail(f"mcp-evidence.json call {idx} must record descriptor_read=true")
        if call.get("outcome") not in {"pass", "fail", "blocked"}:
            fail(f"mcp-evidence.json call {idx} has invalid outcome")


def validate_ledger_snapshot(path: Path) -> None:
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not lines:
        fail("ledger-snapshot.jsonl must contain at least one record")
    for idx, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"ledger-snapshot.jsonl line {idx} is invalid JSON: {exc}")
        if not isinstance(record, dict):
            fail(f"ledger-snapshot.jsonl line {idx} must be an object")


def validate_freshness(bundle: Path, max_age_seconds: int) -> None:
    now = time.time()
    for name in REQUIRED_FILES:
        age = now - (bundle / name).stat().st_mtime
        if age > max_age_seconds:
            fail(f"{name} is stale: {age:.0f}s old, max {max_age_seconds}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=600)
    parser.add_argument("--skip-freshness", action="store_true")
    args = parser.parse_args()

    bundle = args.bundle
    if not bundle.is_dir():
        fail(f"{bundle} is not a directory")
    if not BUNDLE_NAME_RE.match(bundle.name):
        fail(f"bundle name must be date-prefixed lowercase kebab-case: {bundle.name}")

    missing = sorted(name for name in REQUIRED_FILES if not (bundle / name).is_file())
    if missing:
        fail(f"missing required files: {missing}")

    validate_artifacts(bundle / "artifacts.json")
    validate_metrics(bundle / "metrics.json")
    validate_mcp(bundle / "mcp-evidence.json")
    validate_ledger_snapshot(bundle / "ledger-snapshot.jsonl")
    if not args.skip_freshness:
        validate_freshness(bundle, args.max_age_seconds)

    print(f"[validate-evidence-bundle] ok: {bundle}")


if __name__ == "__main__":
    main()
