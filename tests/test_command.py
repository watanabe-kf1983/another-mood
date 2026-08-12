"""Tests for the command boundary types (BuildResult, ResultDiagnostic)."""

from pathlib import Path

import pytest

from another_mood import command
from another_mood.command import BuildResult, ResultDiagnostic
from another_mood.components.shared.component.build_report import ErrorEntry


def _warning(message: str) -> ResultDiagnostic:
    return ResultDiagnostic(
        file="a.yaml", line=1, column=None, message=message, severity="warning"
    )


def _error(message: str) -> ResultDiagnostic:
    return ResultDiagnostic(
        file="a.yaml", line=1, column=None, message=message, severity="error"
    )


class TestBuildResult:
    def test_no_errors_no_warnings_when_empty(self) -> None:
        result = BuildResult(out_dir="x")
        assert result.has_errors() is False
        assert result.has_warnings() is False

    def test_has_errors_when_errors_present(self) -> None:
        result = BuildResult(out_dir="x", errors=(ErrorEntry(message="boom"),))
        assert result.has_errors() is True
        assert result.has_warnings() is False

    def test_has_warnings_when_warning_diagnostic_present(self) -> None:
        result = BuildResult(out_dir="x", diagnostics=(_warning("x-ref dangling"),))
        assert result.has_errors() is False
        assert result.has_warnings() is True

    def test_error_diagnostic_alone_does_not_count_as_warning(self) -> None:
        """``severity="error"`` diagnostics do not flip ``has_warnings``."""
        result = BuildResult(out_dir="x", diagnostics=(_error("schema mismatch"),))
        assert result.has_warnings() is False


class TestHasInternalError:
    def test_false_when_empty(self) -> None:
        assert BuildResult(out_dir="x").has_internal_error() is False

    def test_false_when_only_user_error(self) -> None:
        # A UserError-derived entry carries no traceback.
        result = BuildResult(out_dir="x", errors=(ErrorEntry(message="fix your yaml"),))
        assert result.has_errors() is True
        assert result.has_internal_error() is False

    def test_true_when_any_error_carries_traceback(self) -> None:
        result = BuildResult(
            out_dir="x",
            errors=(
                ErrorEntry(message="fix your yaml"),
                ErrorEntry(message="boom", traceback="Traceback (most recent...)"),
            ),
        )
        assert result.has_internal_error() is True


class TestScaffoldPathContract:
    """A relative path is refused here, not resolved against the process CWD."""

    def test_apply_blueprint_refuses_a_relative_project_dir(self) -> None:
        with pytest.raises(ValueError, match="must be an absolute path"):
            command.apply_blueprint("starter", Path("relative/project"))

    def test_init_refuses_a_relative_project_dir(self) -> None:
        with pytest.raises(ValueError, match="must be an absolute path"):
            command.init(Path("relative/project"))
