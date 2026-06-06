"""Tests for Diagnostic, FileValidationError, and format_pointed."""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    DiagnosticEntry,
    DiagnosticReporter,
    DiagnosticSeverity,
    FileValidationError,
    format_pointed,
)

_FILE = "".join(f"line{n:02}\n" for n in range(1, 21))


class TestDiagnostic:
    def test_defaults(self) -> None:
        d = Diagnostic(file=Path("a.yaml"), line=1, column=None, message="bad")
        assert d.severity == DiagnosticSeverity.error
        assert d.source == ""

    def test_to_entry(self) -> None:
        rel = Path("sub/a.yaml")
        d = Diagnostic(file=rel, line=10, column=3, message="oops", source="normalizer")
        assert d.to_entry() == DiagnosticEntry(
            file=str(rel.resolve()),
            line=10,
            column=3,
            message="oops",
            severity="error",
            source="normalizer",
            snippet="",
        )

    def test_to_entry_with_none_line_column(self) -> None:
        d = Diagnostic(file=Path("a.yaml"), line=None, column=None, message="msg")
        assert d.to_entry() == DiagnosticEntry(
            file=str(Path("a.yaml").resolve()),
            line=None,
            column=None,
            message="msg",
            severity="error",
            source="",
            snippet="",
        )

    def test_format_with_none_file_shows_unknown_placeholder(self) -> None:
        d = Diagnostic(file=None, line=None, column=None, message="msg")
        assert d.format() == "  <unknown>: msg"

    def test_to_entry_with_none_file_serializes_to_empty_string(self) -> None:
        d = Diagnostic(file=None, line=None, column=None, message="msg")
        assert d.to_entry() == DiagnosticEntry(
            file="",
            line=None,
            column=None,
            message="msg",
            severity="error",
            source="",
            snippet="",
        )


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

    def test_returns_empty_when_file_is_none(self) -> None:
        d = Diagnostic(file=None, line=1, column=1, message="x")
        assert d.snippet() == ""


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

    def test_diagnostic_entries(self) -> None:
        rel = Path("a.yaml")
        diags = [
            Diagnostic(file=rel, line=5, column=2, message="bad", source="test"),
        ]
        exc = FileValidationError(diags)
        assert list(exc.diagnostic_entries) == [
            DiagnosticEntry(
                file=str(rel.resolve()),
                line=5,
                column=2,
                message="bad",
                severity="error",
                source="test",
                snippet="",
            ),
        ]


class TestDiagnosticReporter:
    def test_starts_empty(self) -> None:
        reporter = DiagnosticReporter()
        assert reporter.diagnostics == ()

    def test_buffers_reports_in_order(self) -> None:
        reporter = DiagnosticReporter()
        a = Diagnostic(
            file=None,
            line=None,
            column=None,
            message="first",
            severity=DiagnosticSeverity.warning,
        )
        b = Diagnostic(
            file=None,
            line=None,
            column=None,
            message="second",
            severity=DiagnosticSeverity.warning,
        )
        reporter.report(a)
        reporter.report(b)
        assert reporter.diagnostics == (a, b)

    def test_snapshot_is_immutable_view(self) -> None:
        """Mutating the snapshot must not affect future reports."""
        reporter = DiagnosticReporter()
        snapshot = reporter.diagnostics
        reporter.report(
            Diagnostic(
                file=None,
                line=None,
                column=None,
                message="x",
                severity=DiagnosticSeverity.warning,
            )
        )
        assert snapshot == ()
        assert len(reporter.diagnostics) == 1


class TestFormatPointed:
    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param(
                {"line": 4, "column": 5},
                dedent("""\
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |     ^
                      5 | line05
                      6 | line06"""),
                id="normal_with_column",
            ),
            pytest.param(
                {"line": 4, "column": 5, "lines_above": 3, "lines_below": 1},
                dedent("""\
                      1 | line01
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |     ^
                      5 | line05"""),
                id="asymmetric_3_above_1_below",
            ),
            pytest.param(
                {"line": 4, "column": None},
                dedent("""\
                      2 | line02
                      3 | line03
                    > 4 | line04
                      5 | line05
                      6 | line06"""),
                id="normal_without_column",
            ),
            pytest.param(
                {"line": None, "column": 5},
                "",
                id="line_none_returns_empty",
            ),
            pytest.param(
                {"line": 1, "column": 3},
                dedent("""\
                    > 1 | line01
                        |   ^
                      2 | line02
                      3 | line03"""),
                id="top_of_file",
            ),
            pytest.param(
                {"line": 20, "column": 2},
                dedent("""\
                      18 | line18
                      19 | line19
                    > 20 | line20
                         |  ^"""),
                id="bottom_of_file",
            ),
            pytest.param(
                {"line": 100, "column": 1},
                "",
                id="line_beyond_file_returns_empty",
            ),
            pytest.param(
                {"line": 4, "column": 10},
                dedent("""\
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |          ^
                      5 | line05
                      6 | line06"""),
                id="column_beyond_line_end",
            ),
            pytest.param(
                {"line": 4, "column": 2, "lines_above": 0},
                dedent("""\
                    > 4 | line04
                        |  ^
                      5 | line05
                      6 | line06"""),
                id="lines_above_zero",
            ),
            pytest.param(
                {"line": 4, "column": 2, "lines_below": 0},
                dedent("""\
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |  ^"""),
                id="lines_below_zero",
            ),
            pytest.param(
                {"line": 4, "column": 2, "lines_above": 0, "lines_below": 0},
                dedent("""\
                    > 4 | line04
                        |  ^"""),
                id="lines_above_and_below_zero",
            ),
            pytest.param(
                {"line": 9, "column": 2},
                dedent("""\
                       7 | line07
                       8 | line08
                    >  9 | line09
                         |  ^
                      10 | line10
                      11 | line11"""),
                id="gutter_padding_marker_on_single_digit_line",
            ),
            pytest.param(
                {"line": 10, "column": 2},
                dedent("""\
                       8 | line08
                       9 | line09
                    > 10 | line10
                         |  ^
                      11 | line11
                      12 | line12"""),
                id="gutter_padding_marker_on_double_digit_line",
            ),
        ],
    )
    def test_format_pointed(self, kwargs: dict[str, int | None], expected: str) -> None:
        assert format_pointed(file_text=_FILE, **kwargs) == expected  # type: ignore[arg-type]

    def test_single_line_file(self) -> None:
        result = format_pointed(line=1, column=3, file_text="single")
        assert result == dedent("""\
            > 1 | single
                |   ^""")

    def test_empty_file_returns_empty(self) -> None:
        assert format_pointed(line=1, column=1, file_text="") == ""
