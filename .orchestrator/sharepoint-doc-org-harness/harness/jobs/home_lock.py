"""Per-home locks so harvest and relabel do not walk the same tree."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HomeBusy(RuntimeError):
    """A requested home already has a live writer."""


def lock_dir_for_journal(journal_path: Path) -> Path:
    return Path(journal_path).parent / "home_locks"


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lock_path(lock_dir: Path, home: str) -> Path:
    safe = home.replace("/", "_").replace("\\", "_")
    return lock_dir / f"{safe}.lock"


def read_lock(lock_dir: Path, home: str) -> dict[str, Any] | None:
    path = _lock_path(lock_dir, home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def live_locks(lock_dir: Path, *, job: str | None = None) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if not lock_dir.is_dir():
        return found
    for path in lock_dir.glob("*.lock"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = int(data.get("pid") or 0)
        if not pid_is_alive(pid):
            continue
        if job is not None and str(data.get("job") or "") != job:
            continue
        home = str(data.get("home") or path.stem)
        found[home] = data
    return found


def live_relabel_homes(lock_dir: Path) -> list[str]:
    return sorted(live_locks(lock_dir, job="relabel"))


def home_of(rel: str) -> str:
    return rel.replace("\\", "/").strip("/").split("/", 1)[0]


@dataclass
class HomeLockSet:
    lock_dir: Path
    homes: list[str]
    job: str
    pid: int
    _held: list[str] | None = None

    def acquire(self) -> None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        held: list[str] = []
        try:
            for home in self.homes:
                existing = read_lock(self.lock_dir, home)
                if existing is not None:
                    other_pid = int(existing.get("pid") or 0)
                    if pid_is_alive(other_pid) and other_pid != self.pid:
                        raise HomeBusy(
                            f"{home} locked by {existing.get('job')} pid={other_pid}"
                        )
                payload = {
                    "home": home,
                    "job": self.job,
                    "pid": self.pid,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
                path = _lock_path(self.lock_dir, home)
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                held.append(home)
        except Exception:
            for home in held:
                _lock_path(self.lock_dir, home).unlink(missing_ok=True)
            raise
        self._held = held

    def release(self) -> None:
        for home in self._held or self.homes:
            path = _lock_path(self.lock_dir, home)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if int(data.get("pid") or 0) == self.pid and str(data.get("job") or "") == self.job:
                path.unlink(missing_ok=True)
        self._held = None
