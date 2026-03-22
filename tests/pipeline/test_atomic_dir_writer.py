"""Tests for AtomicDirWriter — atomic output with ordering guarantees."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reqs_builder.pipeline.atomic_dir_writer import (
    AtomicDirWriter,
    DirWriterFn,
    VersionInfo,
)


def _write(content: str) -> DirWriterFn:
    """Create a processFn that writes a single file."""

    def fn(out_dir: Path) -> None:
        (out_dir / "result.txt").write_text(content)

    return fn


class TestAtomicDirWriterBasic:
    def test_output_contains_result(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        AtomicDirWriter(out, _write("hello")).run()
        assert (out / "result.txt").read_text() == "hello"

    def test_creates_version_json(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        before = datetime.now(timezone.utc)
        AtomicDirWriter(out, _write("x")).run()
        after = datetime.now(timezone.utc)

        info = json.loads((tmp_path / "output.version.json").read_text())
        ts = datetime.fromisoformat(info["startTime"])
        assert before <= ts <= after

    def test_replaces_entire_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        AtomicDirWriter(out, _write("first")).run()
        assert (out / "result.txt").read_text() == "first"

        def write_different(out_dir: Path) -> None:
            (out_dir / "other.txt").write_text("second")

        AtomicDirWriter(out, write_different).run()
        assert (out / "other.txt").read_text() == "second"
        assert not (out / "result.txt").exists()


class TestAtomicDirWriterOrdering:
    def test_stale_result_is_discarded(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        AtomicDirWriter(out, _write("original")).run()

        # Simulate a future version already completed
        (tmp_path / "output.version.json").write_text(
            json.dumps({"startTime": "2099-01-01T00:00:00+00:00"})
        )

        AtomicDirWriter(out, _write("stale")).run()
        assert (out / "result.txt").read_text() == "original"


class TestAtomicDirWriterCleanup:
    def test_no_tmp_dirs_left(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        AtomicDirWriter(out, _write("x")).run()

        siblings = {p.name for p in tmp_path.iterdir() if p.name.startswith("output")}
        assert siblings == {"output", "output.version.json"}

    def test_lock_is_released(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        AtomicDirWriter(out, _write("first")).run()
        AtomicDirWriter(out, _write("second")).run()
        assert (out / "result.txt").read_text() == "second"


class TestVersionInfo:
    def test_roundtrip(self) -> None:
        info = VersionInfo(start_time=datetime(2026, 3, 22, tzinfo=timezone.utc))
        data: dict[str, Any] = json.loads(info.to_json())
        assert data["startTime"] == "2026-03-22T00:00:00+00:00"
        assert VersionInfo.from_json(json.dumps(data)).start_time == info.start_time

    def test_from_nonexistent_file(self, tmp_path: Path) -> None:
        assert VersionInfo.from_file(tmp_path / "nonexistent.json") is None
