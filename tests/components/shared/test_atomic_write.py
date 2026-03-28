"""Tests for with_atomic_write — atomic output with ordering guarantees."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reqs_builder.components.shared.atomic_write import VersionInfo
from reqs_builder.components.shared.component import Component, with_atomic_write


def _writer(content: str, filename: str = "result.txt") -> Any:
    """Create a component that writes a single file."""

    @with_atomic_write
    @Component(out_dir="out_dir", input_dirs=[])
    def write_fn(*, out_dir: Path) -> None:
        (out_dir / filename).write_text(content)

    return write_fn


class TestAtomicWriteBasic:
    def test_output_contains_result(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        _writer("hello")(out_dir=out)
        assert (out / "result.txt").read_text() == "hello"

    def test_creates_version_json(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        before = datetime.now(timezone.utc)
        _writer("x")(out_dir=out)
        after = datetime.now(timezone.utc)

        info = json.loads((tmp_path / "output.version.json").read_text())
        ts = datetime.fromisoformat(info["startTime"])
        assert before <= ts <= after

    def test_replaces_entire_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        _writer("first")(out_dir=out)
        assert (out / "result.txt").read_text() == "first"

        _writer("second", filename="other.txt")(out_dir=out)
        assert (out / "other.txt").read_text() == "second"
        assert not (out / "result.txt").exists()


class TestAtomicWriteOrdering:
    def test_stale_result_is_discarded(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        _writer("original")(out_dir=out)

        # Simulate a future version already completed
        (tmp_path / "output.version.json").write_text(
            json.dumps({"startTime": "2099-01-01T00:00:00+00:00"})
        )

        _writer("stale")(out_dir=out)
        assert (out / "result.txt").read_text() == "original"


class TestAtomicWriteCleanup:
    def test_no_tmp_dirs_left(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        _writer("x")(out_dir=out)

        siblings = {p.name for p in tmp_path.iterdir() if p.name.startswith("output")}
        assert siblings == {"output", "output.version.json"}

    def test_lock_is_released(self, tmp_path: Path) -> None:
        out = tmp_path / "output"
        _writer("first")(out_dir=out)
        _writer("second")(out_dir=out)
        assert (out / "result.txt").read_text() == "second"


class TestVersionInfo:
    def test_roundtrip(self) -> None:
        info = VersionInfo(start_time=datetime(2026, 3, 22, tzinfo=timezone.utc))
        data: dict[str, Any] = json.loads(info.to_json())
        assert data["startTime"] == "2026-03-22T00:00:00+00:00"
        assert VersionInfo.from_json(json.dumps(data)).start_time == info.start_time

    def test_from_nonexistent_file(self, tmp_path: Path) -> None:
        assert VersionInfo.from_file(tmp_path / "nonexistent.json") is None
