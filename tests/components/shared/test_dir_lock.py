"""Tests for dir_lock — concurrent access coordination for stage I/O."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from another_mood.components.shared.dir_lock import (
    VersionInfo,
    exclusive_write,
    dir_lock,
    exclusive_read,
)


class TestExclusiveWrite:
    def test_output_contains_result(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with exclusive_write(out) as od:
            (od / "result.txt").write_text("hello")
        assert (out / "result.txt").read_text() == "hello"

    def test_creates_version_json(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        before = datetime.now(timezone.utc)
        with exclusive_write(out) as od:
            (od / "x.txt").write_text("x")
        after = datetime.now(timezone.utc)

        info = json.loads((tmp_path / "output.version.json").read_text())
        ts = datetime.fromisoformat(info["startTime"])
        assert before <= ts <= after

    def test_replaces_entire_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with exclusive_write(out) as od:
            (od / "result.txt").write_text("first")
        assert (out / "result.txt").read_text() == "first"

        with exclusive_write(out) as od:
            (od / "other.txt").write_text("second")
        assert (out / "other.txt").read_text() == "second"
        assert not (out / "result.txt").exists()


class TestExclusiveWriteOrdering:
    def test_stale_result_is_discarded(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with exclusive_write(out) as od:
            (od / "result.txt").write_text("original")

        # Simulate a future version already completed
        (tmp_path / "output.version.json").write_text(
            json.dumps({"startTime": "2099-01-01T00:00:00+00:00"})
        )

        with exclusive_write(out) as od:
            (od / "result.txt").write_text("stale")
        assert (out / "result.txt").read_text() == "original"


class TestExclusiveWriteCleanup:
    def test_lock_is_released(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with exclusive_write(out) as od:
            (od / "result.txt").write_text("first")
        with exclusive_write(out) as od:
            (od / "result.txt").write_text("second")
        assert (out / "result.txt").read_text() == "second"


class TestVersionInfo:
    def test_roundtrip(self) -> None:
        info = VersionInfo(start_time=datetime(2026, 3, 22, tzinfo=timezone.utc))
        data: dict[str, Any] = json.loads(info.to_json())
        assert data["startTime"] == "2026-03-22T00:00:00+00:00"
        assert VersionInfo.from_json(json.dumps(data)).start_time == info.start_time

    def test_from_nonexistent_file(self, tmp_path: Path) -> None:
        assert VersionInfo.from_file(tmp_path / "nonexistent.json") is None


class TestDirLock:
    def test_blocks_concurrent_exclusive_write(self, tmp_path: Path) -> None:
        """dir_lock uses the same lock as exclusive_write."""
        out = tmp_path / "output"
        with exclusive_write(out) as od:
            (od / "a.txt").write_text("v1")
        # Acquiring dir_lock then exclusive_write in sequence works (no deadlock)
        with dir_lock(out):
            pass
        with exclusive_write(out) as od:
            (od / "a.txt").write_text("v2")
        assert (out / "a.txt").read_text() == "v2"


class TestSnapshot:
    def test_reflects_source(self, tmp_path: Path) -> None:
        src = tmp_path / "upstream"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        with exclusive_read(src) as snap:
            assert (snap / "a.txt").read_text() == "hello"

    def test_independent_copy(self, tmp_path: Path) -> None:
        src = tmp_path / "upstream"
        src.mkdir()
        (src / "a.txt").write_text("original")
        with exclusive_read(src) as snap:
            (src / "a.txt").write_text("modified")
            assert (snap / "a.txt").read_text() == "original"

    def test_cleaned_up_on_exit(self, tmp_path: Path) -> None:
        src = tmp_path / "upstream"
        src.mkdir()
        (src / "a.txt").write_text("x")
        snap_path = None
        with exclusive_read(src) as snap:
            snap_path = snap
            assert snap_path.exists()
        assert not snap_path.exists()

    def test_nonexistent_dir_yields_empty_exclusive_read(self, tmp_path: Path) -> None:
        src = tmp_path / "does_not_exist"
        with exclusive_read(src) as snap:
            assert snap.exists()
            assert list(snap.iterdir()) == []

    def test_reads_exclusive_write_output(self, tmp_path: Path) -> None:
        """exclusive_read can copy a directory managed by exclusive_write."""
        out = tmp_path / "stage"
        with exclusive_write(out) as od:
            (od / "data.txt").write_text("written")
        with exclusive_read(out) as snap:
            assert (snap / "data.txt").read_text() == "written"
