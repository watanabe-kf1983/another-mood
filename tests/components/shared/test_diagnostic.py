"""Tests for Diagnostic, FileValidationError, and report_data."""

from pathlib import Path

from another_mood.components.shared.diagnostic import (
    Diagnostic,
    DiagnosticSeverity,
    FileValidationError,
)


class TestDiagnostic:
    def test_defaults(self) -> None:
        d = Diagnostic(file=Path("a.yaml"), line=1, column=None, message="bad")
        assert d.severity == DiagnosticSeverity.error
        assert d.source == ""

    def test_to_data(self) -> None:
        rel = Path("sub/a.yaml")
        d = Diagnostic(file=rel, line=10, column=3, message="oops", source="normalizer")
        assert d.to_data() == {
            "file": str(rel.resolve()),
            "line": 10,
            "column": 3,
            "message": "oops",
            "severity": "error",
            "source": "normalizer",
        }

    def test_to_data_with_none_line_column(self) -> None:
        d = Diagnostic(file=Path("a.yaml"), line=None, column=None, message="msg")
        assert d.to_data() == {
            "file": str(Path("a.yaml").resolve()),
            "line": None,
            "column": None,
            "message": "msg",
            "severity": "error",
            "source": "",
        }


class TestFileValidationError:
    def test_message_singular(self) -> None:
        exc = FileValidationError(
            [
                Diagnostic(file=Path("a.yaml"), line=1, column=None, message="bad"),
            ]
        )
        assert str(exc) == "1 validation error"

    def test_message_plural(self) -> None:
        exc = FileValidationError(
            [
                Diagnostic(file=Path("a.yaml"), line=1, column=None, message="bad"),
                Diagnostic(file=Path("b.yaml"), line=2, column=None, message="worse"),
            ]
        )
        assert str(exc) == "2 validation errors"

    def test_report_data(self) -> None:
        rel = Path("a.yaml")
        diags = [
            Diagnostic(file=rel, line=5, column=2, message="bad", source="test"),
        ]
        exc = FileValidationError(diags)
        assert exc.report_data == {
            "errors": [{"message": "FileValidationError: 1 validation error"}],
            "diagnostics": [
                {
                    "file": str(rel.resolve()),
                    "line": 5,
                    "column": 2,
                    "message": "bad",
                    "severity": "error",
                    "source": "test",
                }
            ],
        }
