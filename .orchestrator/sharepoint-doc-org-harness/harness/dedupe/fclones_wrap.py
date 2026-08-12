from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DuplicateGroup:
    sha256: str
    paths: list[Path]


def plan_from_hash_map(groups: dict[str, list[Path]]) -> list[DuplicateGroup]:
    """Build duplicate groups from a precomputed hash→paths map (test/fclones adapter)."""
    out: list[DuplicateGroup] = []
    for digest, paths in groups.items():
        uniq = sorted({p.resolve() for p in paths}, key=lambda p: str(p))
        if len(uniq) > 1:
            out.append(DuplicateGroup(digest, uniq))
    return out


def run_fclones(paths: list[Path]) -> list[DuplicateGroup]:
    """Wrap fclones when installed; otherwise raise FileNotFoundError."""
    exe = shutil.which("fclones")
    if not exe:
        raise FileNotFoundError("fclones not on PATH")
    # fclones group --format json
    cmd = [exe, "group", "--format", "json", *[str(p) for p in paths]]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    # Parser intentionally minimal — production can harden against fclones JSON schema.
    data = json.loads(proc.stdout or "[]")
    groups: list[DuplicateGroup] = []
    if isinstance(data, list):
        for item in data:
            files = item.get("files") or item.get("paths") or []
            digest = str(item.get("hash") or item.get("sha256") or "")
            paths_out = [Path(f) for f in files]
            if digest and len(paths_out) > 1:
                groups.append(DuplicateGroup(digest, paths_out))
    return groups


def apply_duplicate_plan(
    groups: list[DuplicateGroup],
    *,
    delete_duplicates: bool,
    journal_record,
) -> list[dict]:
    """Keep first path; tombstone or delete the rest per policy."""
    actions: list[dict] = []
    for g in groups:
        keep, *dupes = g.paths
        for d in dupes:
            payload = {"keep": str(keep), "duplicate": str(d), "sha256": g.sha256}
            if delete_duplicates and d.exists():
                d.unlink()
                journal_record("delete_duplicate", payload)
                actions.append({"action": "delete", **payload})
            else:
                journal_record("tombstone", payload)
                actions.append({"action": "tombstone", **payload})
    return actions
