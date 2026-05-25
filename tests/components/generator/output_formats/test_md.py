"""Tests for the ``md`` OutputFormat helpers."""

from markupsafe import Markup

from another_mood.components.generator.output_formats.md import (
    MD,
    as_url,
    code_fenced,
    code_inline,
    in_cell,
    md_escape,
)
from another_mood.components.generator.template_engine import make_environment


class TestMdEscape:
    def test_leaves_whitespace_unescaped(self) -> None:
        assert md_escape("# hi") == "\\# hi"

    def test_escapes_each_ascii_punctuation(self) -> None:
        punctuation = (
            "!\"#$%&'()*+,-./"  # 0x21–0x2F
            ":;<=>?@"  # 0x3A–0x40
            "[\\]^_`"  # 0x5B–0x60
            "{|}~"  # 0x7B–0x7E
        )
        assert md_escape(punctuation) == "".join("\\" + c for c in punctuation)

    def test_leaves_alphanumerics_untouched(self) -> None:
        assert md_escape("abc XYZ 123") == "abc XYZ 123"

    def test_leaves_non_ascii_untouched(self) -> None:
        assert md_escape("見出し — テスト") == "見出し — テスト"

    def test_escapes_backslash_itself(self) -> None:
        assert md_escape("\\") == "\\\\"

    def test_empty_string(self) -> None:
        assert md_escape("") == ""


class TestMdOutputFormat:
    def test_name_is_md(self) -> None:
        assert MD.name == "md"

    def test_escape_applies_md_escape(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value }}")
        assert template.render(value="a|b") == "a\\|b"

    def test_markup_bypasses_md_escape(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value | safe }}")
        assert template.render(value="# heading") == "# heading"

    def test_registers_code_inline_as_global(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ code_inline(value) }}")
        assert template.render(value="x") == "`x`"

    def test_registers_code_fenced_as_global(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ code_fenced(value, 'py') }}")
        assert template.render(value="x = 1") == "```py\nx = 1\n```"

    def test_registers_in_cell_as_filter(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value | in_cell }}")
        assert template.render(value="a|b") == "a\\|b"

    def test_registers_as_url_as_filter(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value | as_url }}")
        assert template.render(value="a b") == "a%20b"


class TestCodeInline:
    def test_returns_markup(self) -> None:
        assert isinstance(code_inline("x"), Markup)

    def test_simple_value_uses_single_backtick(self) -> None:
        assert code_inline("abc") == "`abc`"

    def test_value_with_single_backtick_run_uses_two_backticks(self) -> None:
        assert code_inline("a`b") == "``a`b``"

    def test_value_with_double_backtick_run_uses_three_backticks(self) -> None:
        assert code_inline("a``b") == "```a``b```"

    def test_picks_longest_run_when_multiple_runs_present(self) -> None:
        assert code_inline("a`b``c```d") == "````a`b``c```d````"

    def test_pads_when_value_starts_with_backtick(self) -> None:
        assert code_inline("`abc") == "`` `abc ``"

    def test_pads_when_value_ends_with_backtick(self) -> None:
        assert code_inline("abc`") == "`` abc` ``"

    def test_pads_empty_value(self) -> None:
        assert code_inline("") == "`  `"

    def test_pads_all_whitespace_value(self) -> None:
        assert code_inline("   ") == "`     `"

    def test_does_not_escape_backslashes(self) -> None:
        # CommonMark 6.1: backslash escapes are not processed inside code spans.
        assert code_inline("a\\n") == "`a\\n`"

    def test_does_not_escape_pipes_or_markdown_punctuation(self) -> None:
        assert code_inline("a|b*c") == "`a|b*c`"

    def test_coerces_non_string_to_str(self) -> None:
        assert code_inline(42) == "`42`"


class TestCodeFenced:
    def test_returns_markup(self) -> None:
        assert isinstance(code_fenced("x"), Markup)

    def test_simple_body_uses_three_backticks(self) -> None:
        assert code_fenced("hello") == "```\nhello\n```"

    def test_writes_language_as_info_string(self) -> None:
        assert code_fenced("x = 1", "python") == "```python\nx = 1\n```"

    def test_omits_info_string_when_language_empty(self) -> None:
        assert code_fenced("x") == "```\nx\n```"

    def test_widens_fence_for_triple_backtick_run(self) -> None:
        assert code_fenced("```\nfoo\n```", "md") == "````md\n```\nfoo\n```\n````"

    def test_widens_fence_for_longer_backtick_run(self) -> None:
        assert code_fenced("a`````b") == "``````\na`````b\n``````"

    def test_preserves_body_ending_newline(self) -> None:
        assert code_fenced("hello\n") == "```\nhello\n```"

    def test_adds_trailing_newline_when_body_missing_it(self) -> None:
        assert code_fenced("hello") == "```\nhello\n```"

    def test_does_not_escape_backslashes(self) -> None:
        assert code_fenced("a\\n") == "```\na\\n\n```"

    def test_coerces_non_string_to_str(self) -> None:
        assert code_fenced(42) == "```\n42\n```"


class TestInCell:
    def test_returns_markup(self) -> None:
        assert isinstance(in_cell("x"), Markup)

    def test_escapes_pipe(self) -> None:
        assert in_cell("a|b") == "a\\|b"

    def test_escapes_other_markdown_punctuation(self) -> None:
        assert in_cell("a_b") == "a\\_b"

    def test_replaces_newline_with_br(self) -> None:
        assert in_cell("a\nb") == "a<br>b"

    def test_replaces_multiple_newlines(self) -> None:
        assert in_cell("a\nb\nc") == "a<br>b<br>c"

    def test_combines_escape_and_newline_replacement(self) -> None:
        assert in_cell("a|b\nc|d") == "a\\|b<br>c\\|d"

    def test_empty_value(self) -> None:
        assert in_cell("") == ""

    def test_coerces_non_string_to_str(self) -> None:
        assert in_cell(42) == "42"


class TestAsUrl:
    def test_returns_markup(self) -> None:
        assert isinstance(as_url("https://example.com/"), Markup)

    def test_percent_encodes_space(self) -> None:
        assert as_url("a b") == "a%20b"

    def test_preserves_url_structural_punctuation(self) -> None:
        assert (
            as_url("https://example.com/path?q=1&r=2#frag")
            == "https://example.com/path?q=1&r=2#frag"
        )

    def test_encodes_parentheses(self) -> None:
        assert as_url("a(b)c") == "a%28b%29c"

    def test_preserves_unreserved(self) -> None:
        assert as_url("AZaz09-._~") == "AZaz09-._~"

    def test_encodes_non_ascii(self) -> None:
        assert as_url("見") == "%E8%A6%8B"

    def test_coerces_non_string_to_str(self) -> None:
        assert as_url(42) == "42"


class TestHelpersBypassFinalizeEscape:
    """Markup return must survive the finalize hook's md_escape."""

    def test_code_inline_backticks_survive_finalize(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ code_inline(value) }}")
        assert template.render(value="x") == "`x`"

    def test_code_fenced_backticks_survive_finalize(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ code_fenced(value) }}")
        assert template.render(value="x") == "```\nx\n```"

    def test_in_cell_br_survives_finalize(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value | in_cell }}")
        assert template.render(value="a\nb") == "a<br>b"

    def test_as_url_percent_survives_finalize(self) -> None:
        env = make_environment(MD)
        template = env.from_string("[label]({{ value | as_url }})")
        assert template.render(value="a b") == "[label](a%20b)"
