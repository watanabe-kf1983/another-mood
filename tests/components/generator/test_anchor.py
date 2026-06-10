# ``_meta`` is a template-public node field, not a Python-protected attribute.
# pyright: reportPrivateUsage=false
"""Tests for anchor — format-agnostic anchor resolution.

The markdown rendering of the source-relative ``href`` / ``link`` filters
is tested with the format that owns them, in ``output_formats/test_md.py``.
"""

from markupsafe import Markup

from another_mood.components.generator.anchor import (
    MissingAnchor,
    anchor_href,
    anchor_label,
    build_anchor_path,
    make_anchor_filters,
    resolve_anchor,
)
from another_mood.components.generator.data_tree import Node, build_anchor_map
from another_mood.components.generator.reports_config import ReportsConfig

# A small two-page tree: members and by_role are each their own page, so
# cross-page links exercise the relative-path computation.
_DATA = {
    "overview": {"title": "Overview"},
    "members": [
        {"id": "alice", "name": "Alice"},
        {"id": "bob", "name": "Bob"},
    ],
    "by_role": [
        {"id": "dev", "role": "Developer"},
    ],
    "prose": [
        {"id": "design/architecture", "title": "Architecture"},
    ],
}
_FILE_PER = ("members.item", "by_role.item", "prose.item")


def _anchors() -> dict[str, Node]:
    return dict(build_anchor_map(_DATA))


def _config() -> ReportsConfig:
    return ReportsConfig(file_per=_FILE_PER)


# ── build_anchor_path ──────────────────────────────────────────────


class TestBuildAnchorPath:
    def test_single_segment(self) -> None:
        assert build_anchor_path("overview") == "/overview"

    def test_multiple_segments(self) -> None:
        assert build_anchor_path("members", "alice") == "/members/alice"

    def test_segment_with_slash_is_escaped(self) -> None:
        # A `/` inside one built segment is percent-encoded — authors use
        # the ready-made form for path-shaped ids (prose).
        assert build_anchor_path("prose", "a/b") == "/prose/a%2Fb"

    def test_non_string_segment_is_stringified(self) -> None:
        assert build_anchor_path("members", 7) == "/members/7"

    def test_ready_made_path_passes_through(self) -> None:
        assert build_anchor_path("/prose/design/architecture") == (
            "/prose/design/architecture"
        )

    def test_root_path_passes_through(self) -> None:
        assert build_anchor_path("/") == "/"

    def test_ready_made_form_needs_a_lone_argument(self) -> None:
        # With extra segments the first arg is treated as a segment, not a
        # ready-made path — and escaped, so the `/` does not split.
        assert build_anchor_path("/a", "b") == "/%2Fa/b"


class TestRawBuildDiscrimination:
    """The leading-`/` raw/build split is unambiguous: a segment built
    from an entity name (never `/`-leading) and the ready-made path of the
    same value resolve to the same node."""

    def test_built_and_ready_made_agree(self) -> None:
        anchors = _anchors()
        built = resolve_anchor(anchors, "members", "alice")
        ready = resolve_anchor(anchors, "/members/alice")
        assert built is ready is anchors["/members/alice"]


# ── resolve_anchor ─────────────────────────────────────────────────


class TestResolveAnchor:
    def test_resolves_to_node(self) -> None:
        anchors = _anchors()
        assert (
            resolve_anchor(anchors, "members", "alice") is (anchors["/members/alice"])
        )

    def test_resolves_ready_made_prose_path(self) -> None:
        anchors = _anchors()
        assert (
            resolve_anchor(anchors, "/prose/design/architecture")
            is (anchors["/prose/design/architecture"])
        )

    def test_missing_yields_missing_anchor(self) -> None:
        result = resolve_anchor(_anchors(), "members", "nobody")
        assert result == MissingAnchor("/members/nobody")

    def test_root_resolves(self) -> None:
        anchors = _anchors()
        assert resolve_anchor(anchors, "/") is anchors["/"]


# ── anchor_label ───────────────────────────────────────────────────


class TestAnchorLabel:
    def test_prefers_title(self) -> None:
        anchors = _anchors()
        assert anchor_label(anchors["/overview"]) == "Overview"

    def test_falls_back_to_name(self) -> None:
        anchors = _anchors()
        assert anchor_label(anchors["/members/alice"]) == "Alice"

    def test_falls_back_to_id(self) -> None:
        anchors = build_anchor_map({"items": [{"id": "only-id"}]})
        assert anchor_label(anchors["/items/only-id"]) == "only-id"

    def test_falls_back_to_anchor_path(self) -> None:
        # An array node carries none of title/name/id.
        anchors = _anchors()
        assert anchor_label(anchors["/members"]) == "/members"

    def test_mapping_without_title_name_id_falls_back_to_anchor_path(self) -> None:
        # A singleton mapping carrying none of the keys uses its path.
        anchors = build_anchor_map({"overview": {"foo": "bar"}})
        assert anchor_label(anchors["/overview"]) == "/overview"

    def test_missing_anchor_renders_its_path(self) -> None:
        assert anchor_label(MissingAnchor("/members/nobody")) == "/members/nobody"

    def test_missing_anchor_str_is_its_path(self) -> None:
        # `{{ anchor(...) }}` with no filter stringifies via __str__.
        assert str(MissingAnchor("/members/nobody")) == "/members/nobody"


# ── anchor_href ────────────────────────────────────────────────────


class TestAnchorHref:
    def test_cross_page_relative_path_with_fragment(self) -> None:
        anchors = _anchors()
        source = anchors["/by_role/dev"]
        target = anchors["/members/alice"]
        assert anchor_href(_config(), source, target) == (
            "../members/alice.md#/members/alice"
        )

    def test_from_root_page(self) -> None:
        anchors = _anchors()
        source = anchors["/"]  # renders on index.md
        target = anchors["/members/alice"]
        assert anchor_href(_config(), source, target) == (
            "members/alice.md#/members/alice"
        )

    def test_same_page_self_link_keeps_filename(self) -> None:
        anchors = _anchors()
        node = anchors["/members/alice"]
        assert anchor_href(_config(), node, node) == "alice.md#/members/alice"

    def test_fragment_always_appended_even_for_page_root(self) -> None:
        anchors = _anchors()
        source = anchors["/"]
        target = anchors["/members/alice"]
        # alice is itself a page root, yet the fragment is not dropped.
        assert anchor_href(_config(), source, target).endswith("#/members/alice")
        # A MissingAnchor has no page/URL — the rendering filters handle that
        # (a broken reference is shown as plain text), so anchor_href is only
        # ever called for resolved nodes and carries no MissingAnchor branch.


# ── make_anchor_filters (format-neutral, context-free) ─────────────


class TestMakeAnchorFilters:
    """The context-free filters need no output format and no render context,
    so they live here rather than with a concrete format."""

    def test_returns_globals_and_filters(self) -> None:
        globals_map, filters_map = make_anchor_filters(_anchors())
        assert set(globals_map) == {"anchor", "anchor_path"}
        assert set(filters_map) == {"anchor", "anchor_path", "label"}

    def test_anchor_filter_resolves_to_node(self) -> None:
        anchors = _anchors()
        _, filters_map = make_anchor_filters(anchors)
        assert filters_map["anchor"]("members", "alice") is anchors["/members/alice"]

    def test_label_filter_selects_display_text(self) -> None:
        anchors = _anchors()
        _, filters_map = make_anchor_filters(anchors)
        assert filters_map["label"](anchors["/members/alice"]) == "Alice"

    def test_anchor_path_filter_returns_markup(self) -> None:
        # Markup so finalize leaves the already-IRI-escaped path untouched.
        _, filters_map = make_anchor_filters(_anchors())
        result = filters_map["anchor_path"]("members", "alice")
        assert isinstance(result, Markup)
        assert result == "/members/alice"
