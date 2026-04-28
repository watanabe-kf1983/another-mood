"""Tests for BuildReport.collect — including DAG-convergence deduplication."""

from pathlib import Path

import yaml

from another_mood.components.shared.component.build_report import BuildReport


def _write_report(dir_: Path, content: dict[str, object]) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "__build_report.yaml").write_text(
        yaml.safe_dump({"__build_report": content})
    )


class TestCollect:
    def test_dedupes_identical_entries_merged_from_multiple_dirs(
        self, tmp_path: Path
    ) -> None:
        # Same upstream error reaches the collector via two different
        # propagation paths (e.g. compose's upstreams contents + inspect).
        err = {"message": "boom"}
        diag = {"file": "a.yaml", "line": 1, "message": "bad"}
        _write_report(tmp_path / "a", {"errors": [err], "diagnostics": [diag]})
        _write_report(tmp_path / "b", {"errors": [err], "diagnostics": [diag]})

        report = BuildReport.collect(tmp_path / "a", tmp_path / "b")

        assert report.to_data() == {"errors": [err], "diagnostics": [diag]}

    def test_keeps_distinct_entries(self, tmp_path: Path) -> None:
        err1 = {"message": "boom"}
        err2 = {"message": "kaboom"}
        _write_report(tmp_path / "a", {"errors": [err1]})
        _write_report(tmp_path / "b", {"errors": [err2]})

        report = BuildReport.collect(tmp_path / "a", tmp_path / "b")

        assert report.to_data() == {"errors": [err1, err2]}
