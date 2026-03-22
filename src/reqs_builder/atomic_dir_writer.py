"""AtomicDirWriter — execute a processing function with atomic output and ordering guarantees.

Wraps a dir_writer_fn call with:
- Atomic output: write to tmpDir, then rename to outputDir
- Ordering: compare startTime to prevent stale results from overwriting newer ones
- Locking: filelock-based lock to prevent concurrent write conflicts
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
    """Ensure atomic directory output with ordering guarantees.

    Bind output_dir and dir_writer_fn at construction time, then call run().
    The dir_writer_fn receives a temporary directory to write into;
    AtomicDirWriter handles the atomic swap to the final output_dir.
    """

    def __init__(self, output_dir: Path, dir_writer_fn: DirWriterFn) -> None:
        self._output_dir = output_dir
        self._dir_writer_fn = dir_writer_fn
        self._version_path = output_dir.parent / f"{output_dir.name}.version.json"
        self._lock_path = output_dir.parent / f"{output_dir.name}.lock"

    def run(self) -> None:
        """Run the processing function with atomic output.

        1. Record startTime
        2. Run dir_writer_fn into a temporary directory
        3. Acquire lock, compare timestamps, swap if newer
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
            self._swap_if_newer(tmp_dir, start_time)
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)

    def _swap_if_newer(self, tmp_dir: Path, start_time: datetime) -> None:
        """Atomically replace outputDir with tmpDir if startTime is newer."""
        lock = FileLock(self._lock_path)

        with lock:
            existing = VersionInfo.from_file(self._version_path)

            if existing is not None and start_time <= existing.start_time:
                return

            if self._output_dir.exists():
                shutil.rmtree(self._output_dir)
            tmp_dir.rename(self._output_dir)

            version_info = VersionInfo(start_time=start_time)
            self._version_path.write_text(version_info.to_json())
