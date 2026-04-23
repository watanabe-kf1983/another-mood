"""Tests for Diagnostic, FileValidationError, and report_data."""

from pathlib import Path

from another_mood.components.shared.diagnostic import (
    Diagnostic,
    DiagnosticSeverity,
    FileValidationError,
)
from another_mood.components.shared.diagnostic_format import format_pointed


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
            "snippet": "",
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
            "snippet": "",
        }


class TestSnippet:
    def test_normal(self, tmp_path: Path) -> None:
        file = tmp_path / "a.yaml"
        text = "line1\nline2\nline3\n"
        file.write_text(text)
        d = Diagnostic(file=file, line=2, column=3, message="x")
        assert d.snippet() == format_pointed(2, 3, text)

    def test_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        d = Diagnostic(file=tmp_path / "nope.yaml", line=1, column=1, message="x")
        assert d.snippet() == ""

    def test_replaces_non_utf8_bytes(self, tmp_path: Path) -> None:
        file = tmp_path / "a.yaml"
        file.write_bytes(b"line1\n\xff\xfeinvalid\nline3\n")
        d = Diagnostic(file=file, line=2, column=1, message="x")
        assert "�" in d.snippet()


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
                    "snippet": "",
                }
            ],
        }
