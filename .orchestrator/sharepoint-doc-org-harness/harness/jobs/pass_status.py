"""Unstall / restart decision for harvest and relabel passes.

A report with finished_at and a completed home list is DONE even when the
writer pid is dead. Pid-dead plus an unfinished report restarts remaining
homes only. Watchdogs must not re-walk a finished home list.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PassDecision:
    action: str  # done | restart | advance | running
    homes: list[str]
    completed_homes: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_pass_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"pass report must be an object: {path}")
    return data


def _homes(report: dict[str, Any], requested: list[str] | None) -> list[str]:
    if requested:
        return [h for h in requested if h]
    raw = report.get("homes") or []
    if isinstance(raw, list):
        return [str(h) for h in raw if h]
    return []


def _completed(report: dict[str, Any]) -> list[str]:
    raw = report.get("completed_homes") or []
    if isinstance(raw, list):
        return [str(h) for h in raw if h]
    return []


def decide_pass(
    *,
    report: dict[str, Any],
    pid_alive: bool | None = None,
    requested_homes: list[str] | None = None,
    next_homes: list[str] | None = None,
) -> PassDecision:
    """Decide whether a harvest/relabel pass is DONE, should restart, or advance."""
    finished_at = str(report.get("finished_at") or "").strip()
    completed = _completed(report)
    homes = _homes(report, requested_homes)
    incomplete = [h for h in homes if h not in completed]
    pass_complete = bool(finished_at) and not incomplete

    if pass_complete:
        nxt = [h for h in (next_homes or []) if h]
        if nxt:
            return PassDecision(
                action="advance",
                homes=nxt,
                completed_homes=completed,
                reason="completed_pass_advance",
            )
        return PassDecision(
            action="done",
            homes=[],
            completed_homes=completed,
            reason="completed_pass",
        )

    if pid_alive:
        return PassDecision(
            action="running",
            homes=incomplete or homes,
            completed_homes=completed,
            reason="pid_alive",
        )

    restart = incomplete or homes
    return PassDecision(
        action="restart",
        homes=restart,
        completed_homes=completed,
        reason="pid_dead_unfinished",
    )
