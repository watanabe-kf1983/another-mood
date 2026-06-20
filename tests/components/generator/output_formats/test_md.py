"""Tests for the ``md`` OutputFormat helpers."""

from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from another_mood.components.generator.data_tree import Node, build_node_map
from another_mood.components.generator.data_tree_filters import (
    MissingNode,
    make_data_tree_filters,
)
from another_mood.components.generator.output_formats.md import (
    MD,
    MD_FILTERS,
    MD_GLOBALS,
    as_url,
    code_fenced,
    code_inline,
    dedent,
    in_cell,
    make_link_filters,
    md_anchor,
    md_escape,
    md_link,
    stamp_anchor,
    under_heading,
)
from another_mood.components.generator.reports_config import ReportsConfig
from another_mood.components.generator.template_engine import (
    TemplateEngine,
    make_environment,
)


def _md_env() -> Environment:
    """An env with MD's escape / whitespace plus its injected static helpers —
    what a render gets, since the generator injects ``MD_FILTERS`` / ``MD_GLOBALS``."""
    env = make_environment(MD)
    env.filters.update(MD_FILTERS)
    env.globals.update(MD_GLOBALS)  # pyright: ignore[reportCallIssue, reportArgumentType]
    return env


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

    def test_globals_are_the_call_style_helpers(self) -> None:
        assert set(MD_GLOBALS) == {"code_inline", "code_fenced"}

    def test_filters_are_the_binding_free_helpers(self) -> None:
        assert set(MD_FILTERS) == {"in_cell", "as_url", "dedent", "under_heading"}


class TestDedent:
    def test_strips_common_leading_whitespace(self) -> None:
        assert dedent("    a\n    b\n") == "a\nb\n"

    def test_keeps_relative_indentation(self) -> None:
        assert dedent("    a\n        b\n") == "a\n    b\n"

    def test_ignores_blank_lines_in_common_prefix(self) -> None:
        assert dedent("    a\n\n    b\n") == "a\n\nb\n"


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


class TestMdAnchor:
    def test_returns_markup(self) -> None:
        assert isinstance(
            md_anchor(build_node_map(_ANCHOR_DATA)["/members/alice"]), Markup
        )

    def test_emits_closed_anchor_with_node_anchor_path(self) -> None:
        node = build_node_map(_ANCHOR_DATA)["/members/alice"]
        # The id reuses the node's anchor path — the same string href puts in
        # the fragment — so the two ends of a link match by construction.
        assert md_anchor(node) == '<a id="/members/alice"></a>'

    def test_missing_node_emits_nothing(self) -> None:
        # A non-node has no anchor path for any href to target, so anchoring it
        # would be unreachable; like href, it renders empty.
        assert md_anchor(MissingNode("/members/ghost")) == ""


class TestMdPostProcess:
    """The format's render post-pass stamps a node subject's own anchor at the
    top of its output (C9), and leaves a non-node render untouched."""

    def test_stamps_node_subject_anchor_on_its_own_line(self) -> None:
        node = build_node_map(_ANCHOR_DATA)["/members/alice"]
        # Newline-separated so the anchor cannot glue onto a following heading.
        assert (
            stamp_anchor("# Alice\n", node) == '<a id="/members/alice"></a>\n# Alice\n'
        )

    def test_stamps_root_node_anchor(self) -> None:
        root = build_node_map(_ANCHOR_DATA)["/"]
        assert stamp_anchor("# Index\n", root) == '<a id="/"></a>\n# Index\n'

    def test_non_node_subject_is_returned_untouched(self) -> None:
        # The root render's mapping or a build-report dict has no anchor path,
        # so the output is passed through with nothing prepended.
        assert stamp_anchor("# Hello\n", {"title": "Hello"}) == "# Hello\n"


class TestHelpersBypassFinalizeEscape:
    """Markup return must survive the finalize hook's md_escape."""

    def test_code_inline_backticks_survive_finalize(self) -> None:
        env = _md_env()
        template = env.from_string("{{ code_inline(value) }}")
        assert template.render(value="x") == "`x`"

    def test_code_fenced_backticks_survive_finalize(self) -> None:
        env = _md_env()
        template = env.from_string("{{ code_fenced(value) }}")
        assert template.render(value="x") == "```\nx\n```"

    def test_in_cell_br_survives_finalize(self) -> None:
        env = _md_env()
        template = env.from_string("{{ value | in_cell }}")
        assert template.render(value="a\nb") == "a<br>b"

    def test_as_url_percent_survives_finalize(self) -> None:
        env = _md_env()
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
    """md owns the markdown link filters (``href`` / ``link`` / ``anchor`` /
    ``relink``)."""

    def test_returns_href_link_anchor_and_relink(self) -> None:
        filters_map = make_link_filters(_config(), _anchors())
        assert set(filters_map) == {"href", "link", "anchor", "relink"}


class TestLinkFilterWiring:
    """End-to-end through TemplateEngine, covering only what the unit tests
    can't: filter registration, ``@pass_context`` feeding ``this``, and the
    ``href`` / ``link`` closure branches (override, broken reference).

    Each rendered output opens with the subject node's own anchor — the
    engine's ``post_process`` stamp — so the expectations carry that leading
    ``<a id="{source}"></a>`` line."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        # Like the generator: assemble the bound filters (node-map filters and
        # the markdown link filters) and pass them in.
        globals_map, node_filters = make_data_tree_filters(_anchors())
        return TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            output_format=MD,
            filters={**node_filters, **make_link_filters(_config(), _anchors())},
            globals=globals_map,
            reports_config=_config(),
        )

    def test_link_resolves_source_from_context(self, tmp_path: Path) -> None:
        # Exercises the whole chain: node() global, link filter, and
        # @pass_context reading the source page from the `this` subject.
        engine = self._engine(tmp_path, "{{ node('members', 'alice') | link }}")
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == (
            '<a id="/by_role/dev"></a>\n[Alice](../members/alice.md#/members/alice)'
        )

    def test_href_emits_bare_url(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ node('members', 'alice') | href }}")
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == '<a id="/by_role/dev"></a>\n../members/alice.md#/members/alice'

    def test_link_display_override(self, tmp_path: Path) -> None:
        engine = self._engine(
            tmp_path, "{{ node('members', 'alice') | link('the dev') }}"
        )
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == (
            '<a id="/by_role/dev"></a>\n[the dev](../members/alice.md#/members/alice)'
        )

    def test_unresolved_link_renders_as_plain_text(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ node('members', 'ghost') | link }}")
        result = engine.render("t.md", _anchors()["/"])
        # A broken reference is plain visible text, not a `[..](..)` to a dead
        # URL (the `\/` is md-escaping that CommonMark renders back to `/`).
        assert result == '<a id="/"></a>\n\\/members\\/ghost'

    def test_unresolved_href_is_empty(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "[x]({{ node('members', 'ghost') | href }})")
        result = engine.render("t.md", _anchors()["/"])
        assert result == '<a id="/"></a>\n[x]()'

    def test_anchor_emits_target_unescaped(self, tmp_path: Path) -> None:
        # Registered as a filter, and the `<a id>` Markup survives finalize
        # (md_escape would backslash-escape the `/` and `"`).  The leading
        # `<a id="/">` is the page's own post_process stamp; the body anchor
        # is the manual `| anchor` for a different node.
        engine = self._engine(tmp_path, "{{ node('members', 'alice') | anchor }}")
        result = engine.render("t.md", _anchors()["/"])
        assert result == '<a id="/"></a>\n<a id="/members/alice"></a>'


class TestUnderHeadingFilter:
    """The md.py filter adapter: str coercion, Markup wrapping, template use."""

    def test_wraps_result_as_markup(self) -> None:
        assert isinstance(under_heading("# A", "#"), Markup)

    def test_coerces_a_non_str_piped_value(self) -> None:
        # Jinja can pipe in a Markup (or any object); the adapter str-coerces it.
        assert under_heading(Markup("# A"), "#") == "## A"

    def test_pipe_form_keeps_shifted_markdown_unescaped(self) -> None:
        env = _md_env()
        template = env.from_string('{{ body | under_heading("##") }}')
        # Without the Markup wrap, finalize would backslash-escape the `#`.
        assert template.render(body="# A\n## B") == "### A\n#### B"

    def test_block_filter_form_wraps_embedded_output(self) -> None:
        env = _md_env()
        template = env.from_string(
            '{% filter under_heading("##") %}# Embedded{% endfilter %}'
        )
        assert template.render() == "### Embedded"


class TestRelinkFilterWiring:
    """End-to-end through TemplateEngine: registration, ``@pass_context``
    feeding the source page (``this``), node-map resolution, and the Markup wrap.

    Each output opens with the subject's anchor (the engine's post_process
    stamp), so the expectations carry that leading ``<a id="{source}"></a>``
    line."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        globals_map, node_filters = make_data_tree_filters(_anchors())
        return TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            output_format=MD,
            filters={**node_filters, **make_link_filters(_config(), _anchors())},
            globals=globals_map,
            reports_config=_config(),
        )

    def test_resolves_a_node_link_relative_to_the_source_page(
        self, tmp_path: Path
    ) -> None:
        # The body's `node:` link resolves the same way `node(...) | link` would
        # from this page, and the Markup keeps finalize from escaping `[](...)`.
        engine = self._engine(
            tmp_path, '{{ "see [Alice](node:/members/alice)" | relink }}'
        )
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        assert result == (
            '<a id="/by_role/dev"></a>\nsee [Alice](../members/alice.md#/members/alice)'
        )

    def test_unresolved_node_link_keeps_bracketed_text(self, tmp_path: Path) -> None:
        engine = self._engine(
            tmp_path, '{{ "see [ghost](node:/members/ghost)" | relink }}'
        )
        result = engine.render("t.md", _anchors()["/by_role/dev"])
        # The destination is dropped, leaving the link text visibly bracketed.
        assert result == '<a id="/by_role/dev"></a>\nsee [ghost]'
