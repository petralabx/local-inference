#!/usr/bin/env python3
"""Reject tracked paths that Windows cannot check out."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


FORBIDDEN_CHARACTERS = re.compile(r'[<>:"\\|?*\x00-\x1f]')
RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _tracked_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(message or "git ls-files failed")
    return [
        raw_path.decode(errors="surrogateescape")
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    ]


def _fixture_paths(paths_file: Path) -> list[str]:
    return [
        path
        for path in paths_file.read_text(encoding="utf-8").splitlines()
        if path
    ]


def _violations(path: str) -> list[str]:
    violations: list[str] = []
    for component in path.split("/"):
        if FORBIDDEN_CHARACTERS.search(component):
            violations.append(f"{component!r} contains a forbidden character")
        if component.endswith((".", " ")):
            violations.append(f"{component!r} has a trailing dot or space")
        stem = component.split(".", 1)[0].upper()
        if stem in RESERVED_DEVICE_NAMES:
            violations.append(f"{component!r} uses a reserved Windows device name")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-file",
        type=Path,
        help="Validate newline-delimited fixture paths instead of git-tracked paths",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    try:
        paths = (
            _fixture_paths(args.paths_file)
            if args.paths_file is not None
            else _tracked_paths(repo_root)
        )
    except (OSError, RuntimeError, UnicodeError) as exc:
        print(f"Windows-safe path check failed: {exc}", file=sys.stderr)
        return 2

    failures = [
        (path, violation)
        for path in paths
        for violation in _violations(path)
    ]
    if failures:
        print("Windows-invalid paths:")
        for path, violation in failures:
            print(f"  - {path}: {violation}")
        return 1

    print("tracked paths are Windows-safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
