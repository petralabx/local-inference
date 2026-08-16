from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

from harness.config import PACKAGE_ROOT, load_config
from harness.mail.window import first_pass_since, in_first_pass

CADENCE = PACKAGE_ROOT / "scripts" / "install-organizer-cadence.ps1"


def test_cutover_mail_lookback_is_90_days() -> None:
    cfg = load_config(PACKAGE_ROOT / "config" / "default.yaml")
    assert cfg.mail_lookback_days == 90
    assert cfg.mail_remainder_after_proof is True
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    since = first_pass_since(now, lookback_days=cfg.mail_lookback_days)
    assert (now - since).days == 90
    assert in_first_pass(datetime(2026, 6, 1, tzinfo=timezone.utc), now=now) is True
    assert in_first_pass(datetime(2026, 4, 1, tzinfo=timezone.utc), now=now) is False


def test_cutover_cadence_script_has_four_hour_window() -> None:
    text = CADENCE.read_text(encoding="utf-8")
    for stamp in ("06:00", "10:00", "14:00", "18:00"):
        assert stamp in text
    assert "America/Toronto" in text
    assert "daily" in text


def test_cutover_cadence_dry_run_exits_zero() -> None:
    if sys.platform != "win32":
        return
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CADENCE),
            "-Mode",
            "every-4h",
            "-DryRun",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "06:00,10:00,14:00,18:00" in proc.stdout.replace(" ", "")
    assert "dry-run" in proc.stdout
