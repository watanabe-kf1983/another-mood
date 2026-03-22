"""AtomicDirWriter — execute a processing function with atomic output and ordering guarantees.

Wraps a dir_writer_fn call with:
- Safe output: write to tmpDir, then sync contents to outputDir under lock
- Ordering: compare startTime to prevent stale results from overwriting newer ones
- Locking: filelock-based lock to prevent concurrent write conflicts

The output directory is updated in-place (contents cleared + copied)
rather than replaced via rename so that filesystem watchers keep
tracking the same directory inode.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from typing import Protocol
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock


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


class DirWriterFn(Protocol):
    def __call__(self, out_dir: Path) -> None: ...


class AtomicDirWriter:
    """Ensure safe directory output with ordering guarantees.

    Bind output_dir and dir_writer_fn at construction time, then call run().
    The dir_writer_fn receives a temporary directory to write into;
    AtomicDirWriter syncs the result to output_dir under a file lock.
    If dir_writer_fn fails, output_dir is left untouched.
    """

    def __init__(self, output_dir: Path, dir_writer_fn: DirWriterFn) -> None:
        self._output_dir = output_dir
        self._dir_writer_fn = dir_writer_fn
        self._version_path = output_dir.parent / f"{output_dir.name}.version.json"
        self._lock_path = output_dir.parent / f"{output_dir.name}.lock"

    def run(self) -> None:
        """Run the processing function with safe output.

        1. Record startTime
        2. Run dir_writer_fn into a temporary directory
        3. Acquire lock, compare timestamps, sync if newer
        """
        start_time = datetime.now(timezone.utc)

        self._output_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(
            tempfile.mkdtemp(
                prefix=f"{self._output_dir.name}.",
                dir=self._output_dir.parent,
            )
        )

        try:
            self._dir_writer_fn(tmp_dir)
            self._sync_if_newer(tmp_dir, start_time)
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)

    def _sync_if_newer(self, tmp_dir: Path, start_time: datetime) -> None:
        """Sync tmp_dir contents to output_dir if startTime is newer.

        Clears output_dir contents and copies from tmp_dir, preserving
        the directory itself so filesystem watchers keep working.
        """
        lock = FileLock(self._lock_path)

        with lock:
            existing = VersionInfo.from_file(self._version_path)

            if existing is not None and start_time <= existing.start_time:
                return

            self._output_dir.mkdir(parents=True, exist_ok=True)
            for child in self._output_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            shutil.copytree(tmp_dir, self._output_dir, dirs_exist_ok=True)

            version_info = VersionInfo(start_time=start_time)
            self._version_path.write_text(version_info.to_json())
