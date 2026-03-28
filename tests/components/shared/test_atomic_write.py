"""Tests for atomic_write — atomic output with ordering guarantees."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reqs_builder.components.shared.atomic_write import VersionInfo, atomic_write


class TestAtomicWrite:
    def test_output_contains_result(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with atomic_write(out) as od:
            (od / "result.txt").write_text("hello")
        assert (out / "result.txt").read_text() == "hello"

    def test_creates_version_json(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        before = datetime.now(timezone.utc)
        with atomic_write(out) as od:
            (od / "x.txt").write_text("x")
        after = datetime.now(timezone.utc)

        info = json.loads((tmp_path / "output.version.json").read_text())
        ts = datetime.fromisoformat(info["startTime"])
        assert before <= ts <= after

    def test_replaces_entire_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with atomic_write(out) as od:
            (od / "result.txt").write_text("first")
        assert (out / "result.txt").read_text() == "first"

        with atomic_write(out) as od:
            (od / "other.txt").write_text("second")
        assert (out / "other.txt").read_text() == "second"
        assert not (out / "result.txt").exists()


class TestAtomicWriteOrdering:
    def test_stale_result_is_discarded(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with atomic_write(out) as od:
            (od / "result.txt").write_text("original")

        # Simulate a future version already completed
        (tmp_path / "output.version.json").write_text(
            json.dumps({"startTime": "2099-01-01T00:00:00+00:00"})
        )

        with atomic_write(out) as od:
            (od / "result.txt").write_text("stale")
        assert (out / "result.txt").read_text() == "original"


class TestAtomicWriteCleanup:
    def test_no_tmp_dirs_left(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with atomic_write(out) as od:
            (od / "x.txt").write_text("x")

        siblings = {p.name for p in tmp_path.iterdir() if p.name.startswith("output")}
        assert siblings == {"output", "output.version.json"}

    def test_lock_is_released(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        with atomic_write(out) as od:
            (od / "result.txt").write_text("first")
        with atomic_write(out) as od:
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
