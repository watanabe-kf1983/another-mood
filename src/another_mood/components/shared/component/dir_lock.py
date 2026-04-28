"""Directory lock — concurrent access coordination for stage I/O.

Provides two complementary context managers for pipeline stage
directories that may be read and written by concurrent threads:

- exclusive_write: atomic output — work in a temp dir, then sync to the
  real output under a file lock with ordering guarantees.
- exclusive_read: consistent input — point-in-time copy of an upstream
  directory taken under its lock so readers never see a torn state.

Both share the same lock-path convention (dir_lock).

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


def version_path_for(managed_dir: Path) -> Path:
    """Return the version file path for a directory managed by exclusive_write."""
    return managed_dir.parent / f"{managed_dir.name}.version.json"


@contextmanager
def dir_lock(managed_dir: Path) -> Generator[None, None, None]:
    """Acquire the file lock for a directory managed by exclusive_write."""
    lock_path = managed_dir.parent / f"{managed_dir.name}.lock"
    with FileLock(lock_path):
        yield


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
    version_path = version_path_for(out_dir)

    with dir_lock(out_dir):
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


@contextmanager
def exclusive_read(src: Path) -> Generator[Path, None, None]:
    """Point-in-time copy of a directory managed by exclusive_write.

    Acquires the directory's file lock, copies to a temp dir, then
    releases the lock immediately. The caller reads from the exclusive_read
    without blocking concurrent writes. Cleaned up on exit.
    """
    tmp = Path(tempfile.mkdtemp(prefix=f"{src.name}."))
    try:
        with dir_lock(src):
            if src.exists():
                shutil.copytree(src, tmp, dirs_exist_ok=True)
        yield tmp
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


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
