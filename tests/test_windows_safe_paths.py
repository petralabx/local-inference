from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check-windows-safe-paths.py"
INVALID_PATHS = REPO_ROOT / "tests" / "fixtures" / "windows-invalid-paths.txt"
ORIGINAL_INVALID_PATH = (
    ".discovery/buzz-collab-workspace/candidates/"
    "sha256:b256d09884cfd7ecf3451b01e414190c6212652d504af5a92c727c9545a6643e/"
    "CANDIDATE.md"
)


class WindowsSafePathsTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_known_bad_fixture_exits_nonzero(self):
        result = self._run("--paths-file", str(INVALID_PATHS))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(ORIGINAL_INVALID_PATH, result.stdout)
        self.assertIn("forbidden character", result.stdout)
        self.assertIn("trailing dot or space", result.stdout)
        self.assertIn("reserved Windows device name", result.stdout)

    def test_tracked_repository_paths_exit_zero(self):
        result = self._run()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Windows-safe", result.stdout)


if __name__ == "__main__":
    unittest.main()
