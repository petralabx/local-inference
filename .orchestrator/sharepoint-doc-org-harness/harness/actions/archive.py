from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from harness.identity import content_hash
from harness.journal.store import ActionJournal, apply_move


@dataclass
class ArchiveResult:
    src: Path
    dest: Path | None
    status: str  # archived | skipped
    detail: str


def _mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class ArchiveLane:
    """Archive-in-place: move files older than horizon into `_Archive/<yyyy>/`."""

    def __init__(
        self,
        *,
        root: Path,
        journal: ActionJournal,
        horizon_days: int = 365,
        archive_dirname: str = "_Archive",
    ) -> None:
        self.root = root
        self.journal = journal
        self.horizon_days = horizon_days
        self.archive_dirname = archive_dirname

    def should_archive(self, path: Path, *, now: datetime | None = None) -> bool:
        if not path.is_file():
            return False
        if self.archive_dirname in path.parts:
            return False
        now = now or datetime.now(timezone.utc)
        return _mtime_utc(path) < now - timedelta(days=self.horizon_days)

    def archive_file(
        self,
        src: Path,
        *,
        run_id: str,
        now: datetime | None = None,
    ) -> ArchiveResult:
        if not self.should_archive(src, now=now):
            return ArchiveResult(src, None, "skipped", "within horizon or not a file")
        year = str(_mtime_utc(src).year)
        dest_dir = self.root / self.archive_dirname / year
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            dest = dest_dir / f"{src.stem}__{content_hash(src)[:8]}{src.suffix}"
        digest = content_hash(src)
        apply_move(src, dest)
        self.journal.record(
            run_id,
            "archive",
            {"from": str(src), "to": str(dest), "sha256": digest, "horizon_days": self.horizon_days},
        )
        return ArchiveResult(src, dest, "archived", f">{self.horizon_days}d")
