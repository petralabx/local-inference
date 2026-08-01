#!/usr/bin/env python3
"""Validate VMC AutoPilot Hybrid detector results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_DETECTORS = {
    "detect_scope_drift",
    "detect_plan_drift",
    "detect_evidence_drift",
    "detect_context_drift",
    "detect_model_drift",
}
STATUSES = {"pass", "fail", "not_applicable"}
DECISIONS = {"continue", "replan", "halt"}


def fail(message: str) -> None:
    print(f"[validate-detectors] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_metrics(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        fail("metrics file must contain a JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics_json", type=Path)
    parser.add_argument("--expect-failure", action="store_true")
    args = parser.parse_args()

    data = load_metrics(args.metrics_json)
    metrics = data.get("metrics")
    detectors = data.get("detectors")
    if not isinstance(metrics, dict):
        fail("metrics must be an object")
    if not isinstance(detectors, list):
        fail("detectors must be a list")

    seen: set[str] = set()
    failures = 0
    for idx, detector in enumerate(detectors, start=1):
        if not isinstance(detector, dict):
            fail(f"detector {idx} must be an object")
        name = detector.get("detector")
        status = detector.get("status")
        decision = detector.get("decision")
        metric_key = detector.get("metric_key")
        if not isinstance(name, str) or not name:
            fail(f"detector {idx} missing detector name")
        if status not in STATUSES:
            fail(f"{name}: invalid status {status!r}")
        if decision not in DECISIONS:
            fail(f"{name}: invalid decision {decision!r}")
        if not isinstance(metric_key, str) or metric_key not in metrics:
            fail(f"{name}: metric_key must reference metrics object")
        if not isinstance(detector.get("evidence_ref"), str):
            fail(f"{name}: evidence_ref must be a string")
        if status == "fail":
            failures += 1
            if decision == "continue":
                fail(f"{name}: failing detector cannot continue")
        seen.add(name)

    missing = REQUIRED_DETECTORS - seen
    if missing:
        fail(f"missing required detectors: {sorted(missing)}")
    if args.expect_failure and failures == 0:
        fail("--expect-failure set but no detector failed")
    if data.get("gate_result") == "pass" and failures:
        fail("gate_result=pass is invalid when a detector failed")

    print(f"[validate-detectors] ok: {args.metrics_json}")


if __name__ == "__main__":
    main()
