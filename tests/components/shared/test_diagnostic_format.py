"""Tests for format_pointed — code-frame snippet rendering."""

from textwrap import dedent

import pytest

from another_mood.components.shared.diagnostic_format import format_pointed

_FILE = "".join(f"line{n:02}\n" for n in range(1, 21))


class TestFormatPointed:
    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param(
                {"line": 4, "column": 5},
                dedent("""\
                      1 | line01
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |     ^
                      5 | line05"""),
                id="normal_with_column",
            ),
            pytest.param(
                {"line": 4, "column": None},
                dedent("""\
                      1 | line01
                      2 | line02
                      3 | line03
                    > 4 | line04
                      5 | line05"""),
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
                      2 | line02"""),
                id="top_of_file",
            ),
            pytest.param(
                {"line": 20, "column": 2},
                dedent("""\
                      17 | line17
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
                      1 | line01
                      2 | line02
                      3 | line03
                    > 4 | line04
                        |          ^
                      5 | line05"""),
                id="column_beyond_line_end",
            ),
            pytest.param(
                {"line": 4, "column": 2, "lines_above": 0},
                dedent("""\
                    > 4 | line04
                        |  ^
                      5 | line05"""),
                id="lines_above_zero",
            ),
            pytest.param(
                {"line": 4, "column": 2, "lines_below": 0},
                dedent("""\
                      1 | line01
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
                       6 | line06
                       7 | line07
                       8 | line08
                    >  9 | line09
                         |  ^
                      10 | line10"""),
                id="gutter_padding_marker_on_single_digit_line",
            ),
            pytest.param(
                {"line": 10, "column": 2},
                dedent("""\
                       7 | line07
                       8 | line08
                       9 | line09
                    > 10 | line10
                         |  ^
                      11 | line11"""),
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
