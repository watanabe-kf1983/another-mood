"""Tests for publish — copies component outputs to their public destinations."""

from pathlib import Path
from typing import Any

import yaml

from another_mood.components.publish.publish import publish


def _write(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


class TestPublish:
    def test_multiple_src_dist_pairs(self, tmp_path: Path) -> None:
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        src_a = tmp_path / "src_a_root" / "data"
        src_b = tmp_path / "src_b_root" / "data"
        _write(src_a / "a.md", "A\n")
        _write(src_b / "b.md", "B\n")
        dist_a = tmp_path / "dist_a"
        dist_b = tmp_path / "dist_b"

        publish(
            upstream=upstream,
            out_dir=tmp_path / "out",
            src_dirs=[src_a, src_b],
            dist_dirs=[dist_a, dist_b],
        )

        assert (dist_a / "a.md").read_text() == "A\n"
        assert (dist_b / "b.md").read_text() == "B\n"

    def test_removes_stale_files_in_dist(self, tmp_path: Path) -> None:
        """File in dist but not in src is removed on next publish."""
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        src = tmp_path / "src_root" / "data"
        _write(src / "a.md")
        _write(src / "stale.md")
        dist = tmp_path / "dist"

        publish(
            upstream=upstream,
            out_dir=tmp_path / "out",
            src_dirs=[src],
            dist_dirs=[dist],
        )
        assert (dist / "stale.md").exists()

        (src / "stale.md").unlink()
        publish(
            upstream=upstream,
            out_dir=tmp_path / "out",
            src_dirs=[src],
            dist_dirs=[dist],
        )

        assert (dist / "a.md").exists()
        assert not (dist / "stale.md").exists()

    def test_skips_on_upstream_error(self, tmp_path: Path) -> None:
        upstream = tmp_path / "upstream"
        _write_yaml(
            upstream / "reports" / "__build_report.yaml",
            {"__build_report": {"errors": [{"message": "boom"}]}},
        )
        src = tmp_path / "src_root" / "data"
        _write(src / "a.md", "new\n")
        dist = tmp_path / "dist"
        _write(dist / "previous.md", "old\n")

        publish(
            upstream=upstream,
            out_dir=tmp_path / "out",
            src_dirs=[src],
            dist_dirs=[dist],
        )

        assert (dist / "previous.md").read_text() == "old\n"
        assert not (dist / "a.md").exists()
