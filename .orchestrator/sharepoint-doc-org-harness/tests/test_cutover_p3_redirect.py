from __future__ import annotations

import subprocess
import sys
from harness.config import PACKAGE_ROOT

SCRIPT = PACKAGE_ROOT / "scripts" / "redirect-known-folders.ps1"


def test_cutover_redirect_script_names_capture_folders_and_guards() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "00_Inbox\\_from_desktop" in text
    assert "00_Inbox\\_from_documents" in text
    assert "00_Inbox\\_from_downloads" in text
    assert "DryRun" in text
    assert "Undo" in text
    assert "taylorvalton" in text.lower()
    assert "blocked-until-vince-present" in text


def test_cutover_redirect_dry_run_exits_zero() -> None:
    if sys.platform != "win32":
        return
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-DryRun",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "dry-run" in proc.stdout
    assert "no known-folder change" in proc.stdout
