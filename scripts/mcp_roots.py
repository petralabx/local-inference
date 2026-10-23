"""Resolve MCP source paths without depending on a workstation checkout location."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ENV = "LOCAL_INFERENCE_ROOT"
CONFIG_ENV = "MCP_CONFIG_PATH"
SETTINGS_ENV = "MCP_SETTINGS_PATH"


class RootError(RuntimeError):
    """Invalid explicit source or no discoverable local-inference checkout."""


@dataclass(frozen=True)
class Sources:
    root: Path | None
    config: Path
    settings: Path


def add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        help=f"checkout root (overrides ${ROOT_ENV} and source env defaults)",
    )
    parser.add_argument(
        "--config", type=Path, help=f"MCP config file (overrides ${CONFIG_ENV})"
    )
    parser.add_argument(
        "--settings",
        type=Path,
        help=f"permissions file (overrides ${SETTINGS_ENV}; missing CLI file is optional)",
    )


def _valid_root(root: Path) -> bool:
    # A shipped repository marker also works for deployments without .git.
    marker = root / "config" / "execution-primitives.local.yaml"
    try:
        return (
            root / ".mcp.json"
        ).is_file() and "repo: petralabx/local-inference" in marker.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, ValueError):
        return False


def resolve_sources(
    root: Path | None = None,
    config: Path | None = None,
    settings: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    script_root: Path = SCRIPT_ROOT,
    cwd: Path | None = None,
) -> Sources:
    """CLI > environment > own checkout > CWD git toplevel; never hide bad overrides.

    Explicit config files may be standalone (as before). Explicit --root supplies
    both source defaults and suppresses environment source paths. Settings are
    optional by default and for CLI paths; an environment settings override must exist.
    """
    env = os.environ if env is None else env
    tried: list[str] = []

    def fail(reason: str) -> None:
        raise RootError(
            f"{reason}. Set --root/{ROOT_ENV} to a local-inference checkout "
            f"containing .mcp.json and config/execution-primitives.local.yaml "
            f"(repo: petralabx/local-inference), or --config/{CONFIG_ENV} "
            f"and --settings/{SETTINGS_ENV} to source files. Tried: {'; '.join(tried)}"
        )

    explicit_root = root is not None
    selected_root = root if explicit_root else env.get(ROOT_ENV)
    selected_config = (
        config
        if config is not None
        else (None if explicit_root else env.get(CONFIG_ENV))
    )
    selected_settings = (
        settings
        if settings is not None
        else (None if explicit_root else env.get(SETTINGS_ENV))
    )
    resolved_root = None
    if selected_root is not None:
        resolved_root = Path(selected_root).expanduser().resolve()
        tried.append(f"{'--root' if explicit_root else ROOT_ENV}={resolved_root}")
        if not _valid_root(resolved_root):
            fail("invalid checkout override")
    if selected_config is not None:
        selected_config = Path(selected_config).expanduser().resolve()
        tried.append(
            f"{'--config' if config is not None else CONFIG_ENV}={selected_config}"
        )
        if not selected_config.is_file():
            fail("invalid config override (file missing)")
    if selected_settings is not None:
        selected_settings = Path(selected_settings).expanduser().resolve()
        tried.append(
            f"{'--settings' if settings is not None else SETTINGS_ENV}={selected_settings}"
        )
        if settings is None and not selected_settings.is_file():
            fail("invalid settings override (file missing)")

    # Discover only when source defaults are needed; standalone explicit files work.
    if resolved_root is None:
        candidate = script_root.resolve()
        tried.append(f"script checkout={candidate}")
        if _valid_root(candidate):
            resolved_root = candidate
        elif selected_config is None or selected_settings is None:
            current = (cwd or Path.cwd()).resolve()
            tried.append(f"CWD git toplevel from {current}")
            try:
                result = subprocess.run(
                    ["git", "-C", str(current), "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    candidate = Path(result.stdout.strip()).resolve()
                    tried.append(f"CWD checkout={candidate}")
                    if _valid_root(candidate):
                        resolved_root = candidate
            except OSError:
                tried.append("git unavailable")
    if resolved_root is None and (selected_config is None or selected_settings is None):
        fail("no valid local-inference checkout found")
    return Sources(
        resolved_root,
        selected_config if selected_config is not None else resolved_root / ".mcp.json",
        selected_settings
        if selected_settings is not None
        else resolved_root / ".claude" / "settings.json",
    )
