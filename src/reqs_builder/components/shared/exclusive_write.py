"""Exclusive directory write — context manager.

Provides exclusive output directory updates: work is done in a temporary
directory, then synced to the real output under a file lock with
ordering guarantees.

Design notes:
- The output directory is updated in-place (contents cleared + copied)
  rather than replaced via rename so that filesystem watchers keep
  tracking the same directory inode.
- Timestamps over monotonic counters: system clock is reliable enough
  on a single machine and requires no shared state between processes.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock


@contextmanager
def exclusive_write(out_dir: Path) -> Generator[Path, None, None]:
    """Context manager: write to a temporary directory, then sync exclusively.

    Yields a temporary directory path. On successful exit, the temp dir
    is synced to out_dir under a file lock with ordering guarantees.
    """
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"{out_dir.name}."))

    start_time = datetime.now(timezone.utc)
    try:
        yield tmp_dir
        _sync_if_newer(tmp_dir, out_dir, start_time)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)


def _sync_if_newer(tmp_dir: Path, out_dir: Path, start_time: datetime) -> None:
    """Sync tmp_dir contents to out_dir if startTime is newer."""
    version_path = out_dir.parent / f"{out_dir.name}.version.json"
    lock_path = out_dir.parent / f"{out_dir.name}.lock"
    lock = FileLock(lock_path)

    with lock:
        existing = VersionInfo.from_file(version_path)

        if existing is not None and start_time <= existing.start_time:
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        for child in out_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        shutil.copytree(tmp_dir, out_dir, dirs_exist_ok=True)

        version_info = VersionInfo(start_time=start_time)
        version_path.write_text(version_info.to_json())


@dataclass(frozen=True)
class VersionInfo:
    """Metadata for a stage output (stored in {outputDir}.version.json)."""

    start_time: datetime

    def to_json(self) -> str:
        return json.dumps({"startTime": self.start_time.isoformat()})

    @staticmethod
    def from_json(text: str) -> VersionInfo:
        data = json.loads(text)
        return VersionInfo(start_time=datetime.fromisoformat(data["startTime"]))

    @staticmethod
    def from_file(path: Path) -> VersionInfo | None:
        if not path.exists():
            return None
        return VersionInfo.from_json(path.read_text())
