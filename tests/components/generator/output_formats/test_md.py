"""Tests for the ``md`` OutputFormat helpers."""

from pathlib import Path

from markupsafe import Markup

from another_mood.components.generator.data_tree import Node, build_node_map
from another_mood.components.generator.data_tree_filters import make_data_tree_filters
from another_mood.components.generator.output_formats.md import (
    MD,
    as_url,
    code_fenced,
    code_inline,
    in_cell,
    make_link_filters,
    md_escape,
    md_link,
)
from another_mood.components.generator.reports_config import ReportsConfig
from another_mood.components.generator.template_engine import (
    TemplateEngine,
    make_environment,
)


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

    def test_keeps_ucschar_raw(self) -> None:
        # IRI form: ucschar pass through so CJK URLs stay readable.
        assert as_url("見") == "見"

    def test_coerces_non_string_to_str(self) -> None:
        assert as_url(42) == "42"


class TestMdLink:
    def test_composes_markdown_link(self) -> None:
        assert md_link("Alice", "members/alice.md#/members/alice") == (
            "[Alice](members/alice.md#/members/alice)"
        )

    def test_returns_markup(self) -> None:
        assert isinstance(md_link("x", "y"), Markup)

    def test_escapes_display_text(self) -> None:
        # `|` would otherwise be read as table structure.
        assert md_link("A|B", "u") == "[A\\|B](u)"

    def test_does_not_escape_url(self) -> None:
        # The url is trusted as already URL-safe; md_escape would corrupt it.
        assert md_link("t", "a/b#c") == "[t](a/b#c)"


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


# A small two-page tree: members and by_role are each their own page, so
# cross-page links exercise the relative-path computation.
_ANCHOR_DATA = {
    "members": [
        {"id": "alice", "name": "Alice"},
        {"id": "bob", "name": "Bob"},
    ],
    "by_role": [
        {"id": "dev", "role": "Developer"},
    ],
}
_ANCHOR_FILE_PER = ("members.item", "by_role.item")


def _anchors() -> dict[str, Node]:
    return dict(build_node_map(_ANCHOR_DATA))


def _config() -> ReportsConfig:
    return ReportsConfig(file_per=_ANCHOR_FILE_PER)


class TestMakeLinkFilters:
    """md owns the source-relative link filters (``href`` / ``link``)."""

    def test_returns_href_and_link(self) -> None:
        filters_map = make_link_filters(_config())
        assert set(filters_map) == {"href", "link"}


class TestLinkFilterWiring:
    """End-to-end through TemplateEngine, covering only what the unit tests
    can't: filter registration, ``@pass_context`` feeding ``this``, and the
    ``href`` / ``link`` closure branches (override, broken reference)."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        # Like the generator: pass the format-neutral filters from data_tree_filters;
        # the `href` / `link` filters come from MD itself, wired by the
        # engine from `reports_config`.
        globals_map, node_filters = make_data_tree_filters(_anchors())
        return TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            output_format=MD,
            filters=node_filters,
            globals=globals_map,
            reports_config=_config(),
        )

    def test_link_resolves_source_from_context(self, tmp_path: Path) -> None:
        # Exercises the whole chain: node() global, link filter, and
        # @pass_context reading the source page from the `this` subject.
        engine = self._engine(tmp_path, "{{ node('members', 'alice') | link }}")
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == "[Alice](../members/alice.md#/members/alice)"

    def test_href_emits_bare_url(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ node('members', 'alice') | href }}")
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == "../members/alice.md#/members/alice"

    def test_link_display_override(self, tmp_path: Path) -> None:
        engine = self._engine(
            tmp_path, "{{ node('members', 'alice') | link('the dev') }}"
        )
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == "[the dev](../members/alice.md#/members/alice)"

    def test_unresolved_link_renders_as_plain_text(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ node('members', 'ghost') | link }}")
        result = engine.render("t.md", _anchors()["/"])
        # A broken reference is plain visible text, not a `[..](..)` to a dead
        # URL (the `\/` is md-escaping that CommonMark renders back to `/`).
        assert result == "\\/members\\/ghost"

    def test_unresolved_href_is_empty(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "[x]({{ node('members', 'ghost') | href }})")
        result = engine.render("t.md", _anchors()["/"])
        assert result == "[x]()"
