#!/usr/bin/env python3
"""Validate a VMC AutoPilot Hybrid decision ledger."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


REQUIRED_FIELDS = {
    "ts",
    "phase",
    "iteration",
    "event",
    "plan_hash",
    "decision",
    "rationale",
    "evidence_ref",
    "metrics",
}
PHASES = {"A", "B", "C", "D", "E"}
EVENTS = {"gate_entry", "plan", "exec", "verify", "replan", "gate_exit", "escalate"}


def fail(message: str) -> None:
    print(f"[validate-ledger] {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_ts(value: object, line_no: int) -> datetime:
    if not isinstance(value, str):
        fail(f"line {line_no}: ts must be a string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        fail(f"line {line_no}: invalid ISO-8601 ts: {exc}")


def validate_record(record: object, line_no: int) -> tuple[str, str, datetime]:
    if not isinstance(record, dict):
        fail(f"line {line_no}: record must be an object")
    missing = REQUIRED_FIELDS - set(record)
    if missing:
        fail(f"line {line_no}: missing fields {sorted(missing)}")

    phase = record["phase"]
    event = record["event"]
    if phase not in PHASES:
        fail(f"line {line_no}: invalid phase {phase!r}")
    if event not in EVENTS:
        fail(f"line {line_no}: invalid event {event!r}")
    if not isinstance(record["iteration"], int) or record["iteration"] < 1:
        fail(f"line {line_no}: iteration must be a positive integer")
    if not isinstance(record["plan_hash"], str) or not record["plan_hash"]:
        fail(f"line {line_no}: plan_hash must be a non-empty string")
    if not isinstance(record["decision"], str) or not record["decision"]:
        fail(f"line {line_no}: decision must be a non-empty string")
    if not isinstance(record["rationale"], str) or not record["rationale"]:
        fail(f"line {line_no}: rationale must be a non-empty string")
    if not isinstance(record["evidence_ref"], str) or not record["evidence_ref"]:
        fail(f"line {line_no}: evidence_ref must be a non-empty string")
    if not isinstance(record["metrics"], dict):
        fail(f"line {line_no}: metrics must be an object")

    return str(phase), str(event), parse_ts(record["ts"], line_no)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--allow-open-phase", action="store_true")
    args = parser.parse_args()

    if not args.ledger.is_file():
        fail(f"{args.ledger} is not a file")

    latest_by_phase: dict[str, str] = {}
    saw_entry = False
    previous_ts: datetime | None = None
    lines = [line for line in args.ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        fail("ledger must contain at least one record")

    for line_no, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"line {line_no}: invalid JSON: {exc}")
        phase, event, ts = validate_record(record, line_no)
        if previous_ts is not None and ts < previous_ts:
            fail(f"line {line_no}: timestamps must be append-only/non-decreasing")
        previous_ts = ts
        latest_by_phase[phase] = event
        saw_entry = saw_entry or event == "gate_entry"

    if not saw_entry:
        fail("ledger must include at least one gate_entry record")

    if not args.allow_open_phase:
        open_phases = {
            phase: event
            for phase, event in latest_by_phase.items()
            if event not in {"gate_exit", "escalate"}
        }
        if open_phases:
            fail(f"latest phase records must be terminal at phase exit: {open_phases}")

    print(f"[validate-ledger] ok: {args.ledger}")


if __name__ == "__main__":
    main()
