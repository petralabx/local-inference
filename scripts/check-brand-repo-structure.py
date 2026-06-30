#!/usr/bin/env python3
"""Marketing-brand repo structure gate — validates plx-brand.json and the
PLX-structure design-system bundle without requiring PLX --p-* tokens.

Operational repos (repoKind=operational|platform with adoptsPlxTokens=true) are
checked lightly: plx-brand.json must exist and declare adoption. Marketing-brand
repos (repoKind=marketing-brand or adoptsPlxTokens=false) must also ship the
complete structural bundle documented in docs/runbooks/marketing-brand-repo-setup.md.

Run from a consumer repo root:
    python scripts/check-brand-repo-structure.py
    python scripts/check-brand-repo-structure.py --repo-root /path/to/repo

Exit codes: 0 — clean or no plx-brand.json (skip); 1 — violations found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "plx-brand/v1"

# Structural bundle required for marketing-brand repos (PLX-structure, own tokens).
MARKETING_REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "plx-brand.json",
    "docs/design-system/README.md",
    "docs/design-system/tokens.css",
    "docs/design-system/tokens.ts",
    "docs/design-system/REFERENCE.md",
    "docs/design-system/COMPONENT-INVENTORY.md",
    "docs/design-system/CONTRIBUTING.md",
    "docs/modules/design-system/README.md",
)

MARKETING_REQUIRED_DIRS = ("docs/design-system/decisions",)

# PLX operational token names — marketing repos must not define these as their
# primary layer when adoptsPlxTokens is false.
PLX_TOKEN_DEF_RE = re.compile(
    r"^\s*--p-(?:paper|ink|accent|card|muted|grid)\s*:",
    re.MULTILINE,
)


def _load_manifest(repo_root: Path) -> dict | None:
    path = repo_root / "plx-brand.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"plx-brand.json: invalid JSON — {exc}") from exc


def _require_field(data: dict, key: str, violations: list[str], path: str = "") -> None:
    prefix = f"{path}." if path else ""
    if key not in data or data[key] in (None, ""):
        violations.append(f"plx-brand.json missing required field: {prefix}{key}")


def _validate_manifest_shape(manifest: dict, violations: list[str]) -> str:
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        violations.append(
            f"plx-brand.json schemaVersion must be {SCHEMA_VERSION!r}, "
            f"got {manifest.get('schemaVersion')!r}"
        )

    repo_kind = manifest.get("repoKind")
    if repo_kind not in ("operational", "marketing-brand", "platform"):
        violations.append(
            "plx-brand.json repoKind must be operational, marketing-brand, or platform"
        )

    brand = manifest.get("brand")
    if not isinstance(brand, dict):
        violations.append("plx-brand.json brand must be an object")
    else:
        _require_field(brand, "slug", violations, "brand")
        _require_field(brand, "displayName", violations, "brand")

    ds = manifest.get("designSystem")
    if not isinstance(ds, dict):
        violations.append("plx-brand.json designSystem must be an object")
        return repo_kind or ""

    for key in (
        "adoptsPlxTokens",
        "tokenPrefix",
        "boundaryClass",
        "decidedBy",
        "decidedAt",
        "rationale",
    ):
        _require_field(ds, key, violations, "designSystem")

    if ds.get("adoptsPlxTokens") is True and not ds.get("authority"):
        violations.append(
            "plx-brand.json designSystem.authority required when adoptsPlxTokens is true"
        )

    prefix = ds.get("tokenPrefix", "")
    if prefix and not re.match(r"^--[a-z][a-z0-9-]*-$", str(prefix)):
        violations.append(
            f"designSystem.tokenPrefix must look like --brand- (got {prefix!r})"
        )

    boundary = ds.get("boundaryClass", "")
    if boundary and not re.match(r"^brand-[a-z0-9]+(?:-[a-z0-9]+)*$", str(boundary)):
        violations.append(
            f"designSystem.boundaryClass must look like brand-slug (got {boundary!r})"
        )

    mc = manifest.get("mc")
    if not isinstance(mc, dict):
        violations.append("plx-brand.json mc must be an object")
    else:
        _require_field(mc, "github", violations, "mc")
        _require_field(mc, "registryId", violations, "mc")

    return str(repo_kind or "")


def _is_marketing_brand(manifest: dict) -> bool:
    return manifest.get("repoKind") == "marketing-brand"


def _uses_own_tokens(manifest: dict) -> bool:
    ds = manifest.get("designSystem") or {}
    return ds.get("adoptsPlxTokens") is False


def _check_marketing_files(repo_root: Path, violations: list[str]) -> None:
    for rel in MARKETING_REQUIRED_FILES:
        if not (repo_root / rel).is_file():
            violations.append(f"missing required file: {rel}")

    for rel in MARKETING_REQUIRED_DIRS:
        path = repo_root / rel
        if not path.is_dir():
            violations.append(f"missing required directory: {rel}/")
            continue
        adrs = list(path.glob("ADR-*.md"))
        if not adrs:
            violations.append(f"{rel}/ must contain at least one ADR-*.md")


def _check_token_isolation(
    repo_root: Path, manifest: dict, violations: list[str]
) -> None:
    ds = manifest.get("designSystem") or {}
    prefix = str(ds.get("tokenPrefix") or "")
    tokens_path = repo_root / "docs/design-system/tokens.css"
    if not tokens_path.is_file():
        return

    text = tokens_path.read_text(encoding="utf-8")

    for match in PLX_TOKEN_DEF_RE.finditer(text):
        violations.append(
            f"docs/design-system/tokens.css defines PLX operational token {match.group(0).strip()} "
            "— marketing brands must use their own tokenPrefix, not --p-*"
        )

    if prefix and prefix not in text:
        violations.append(
            f"docs/design-system/tokens.css must declare tokens using {prefix} "
            "(designSystem.tokenPrefix)"
        )

    if re.search(r"@import\s+.*plx-customer-portal", text, re.IGNORECASE):
        violations.append(
            "docs/design-system/tokens.css must not @import plx-customer-portal tokens "
            "when adoptsPlxTokens is false"
        )


def check_repo(repo_root: Path) -> list[str]:
    violations: list[str] = []

    try:
        manifest = _load_manifest(repo_root)
    except ValueError as exc:
        return [str(exc)]

    if manifest is None:
        return []

    repo_kind = _validate_manifest_shape(manifest, violations)

    if _is_marketing_brand(manifest):
        _check_marketing_files(repo_root, violations)
        _check_token_isolation(repo_root, manifest, violations)
    elif _uses_own_tokens(manifest):
        _check_token_isolation(repo_root, manifest, violations)

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root of the repo to validate (default: cwd)",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    violations = check_repo(repo_root)

    if not (repo_root / "plx-brand.json").is_file() and not violations:
        print("brand repo structure: skip (no plx-brand.json)")
        return 0

    if violations:
        print("brand repo structure violations:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("brand repo structure clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
