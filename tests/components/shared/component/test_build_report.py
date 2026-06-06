"""Tests for BuildReport.collect — including DAG-convergence deduplication."""

from pathlib import Path

import yaml

from another_mood.components.shared.component.build_report import (
    BuildReport,
    ErrorEntry,
)
from another_mood.components.shared.user_error import UserError
from another_mood.components.shared.user_source.diagnostic import DiagnosticEntry


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
        diag = {
            "file": "a.yaml",
            "line": 1,
            "column": None,
            "message": "bad",
            "severity": "error",
            "source": "",
            "snippet": "",
        }
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


class TestHasWarnings:
    def test_false_when_empty(self) -> None:
        assert BuildReport().has_warnings() is False

    def test_false_when_only_error_diagnostics(self) -> None:
        report = BuildReport(
            diagnostics=(
                DiagnosticEntry(
                    file="a.yaml", line=1, column=None, message="x", severity="error"
                ),
            )
        )
        assert report.has_warnings() is False

    def test_true_when_warning_diagnostic_present(self) -> None:
        report = BuildReport(
            diagnostics=(
                DiagnosticEntry(
                    file="a.yaml", line=1, column=None, message="x", severity="error"
                ),
                DiagnosticEntry(
                    file="b.yaml", line=2, column=None, message="y", severity="warning"
                ),
            )
        )
        assert report.has_warnings() is True


class TestWithException:
    """``with_exception`` keys traceback inclusion on whether the exception
    is user-facing (exposes ``user_error_message``)."""

    def test_user_facing_error_summary_without_traceback(self) -> None:
        # A UserError with diagnostic_entries -> a summary ErrorEntry (no
        # traceback) plus the carried diagnostics.
        diag = DiagnosticEntry(file="a.yaml", line=1, column=None, message="bad")

        class _UserFacing(UserError):
            diagnostic_entries = (diag,)

        report = BuildReport().with_exception(_UserFacing("1 problem"))

        assert list(report.errors) == [ErrorEntry(message="_UserFacing: 1 problem")]
        assert list(report.diagnostics) == [diag]

    def test_plain_user_error_has_no_diagnostics(self) -> None:
        # A UserError without diagnostic_entries still suppresses the
        # traceback; its guidance is the message alone.
        report = BuildReport().with_exception(UserError("run mood init first"))

        assert list(report.errors) == [
            ErrorEntry(message="UserError: run mood init first")
        ]
        assert list(report.diagnostics) == []

    def test_bug_carries_traceback(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            report = BuildReport().with_exception(exc)

        (error,) = report.errors
        assert error.message == "ValueError: boom"
        assert error.traceback is not None and "ValueError: boom" in error.traceback
        assert list(report.diagnostics) == []
