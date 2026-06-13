# ``_meta`` is a template-public node field, not a Python-protected attribute.
# pyright: reportPrivateUsage=false
"""Tests for data_tree_filters — format-agnostic node resolution.

The markdown rendering of the source-relative ``href`` / ``link`` filters
is tested with the format that owns them, in ``output_formats/test_md.py``.
"""

from another_mood.components.generator.data_tree import Node, build_node_map
from another_mood.components.generator.data_tree_filters import (
    MissingNode,
    build_anchor_path,
    make_data_tree_filters,
    node_href,
    node_label,
    resolve_node,
)
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


def _node_map() -> dict[str, Node]:
    return dict(build_node_map(_DATA))


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
        nodes = _node_map()
        built = resolve_node(nodes, "members", "alice")
        ready = resolve_node(nodes, "/members/alice")
        assert built is ready is nodes["/members/alice"]


# ── resolve_node ─────────────────────────────────────────────────


class TestResolveNode:
    def test_resolves_to_node(self) -> None:
        nodes = _node_map()
        assert resolve_node(nodes, "members", "alice") is (nodes["/members/alice"])

    def test_resolves_ready_made_prose_path(self) -> None:
        nodes = _node_map()
        assert (
            resolve_node(nodes, "/prose/design/architecture")
            is (nodes["/prose/design/architecture"])
        )

    def test_missing_yields_missing_node(self) -> None:
        result = resolve_node(_node_map(), "members", "nobody")
        assert result == MissingNode("/members/nobody")

    def test_root_resolves(self) -> None:
        nodes = _node_map()
        assert resolve_node(nodes, "/") is nodes["/"]


# ── node_label ───────────────────────────────────────────────────


class TestNodeLabel:
    def test_prefers_title(self) -> None:
        nodes = _node_map()
        assert node_label(nodes["/overview"]) == "Overview"

    def test_falls_back_to_name(self) -> None:
        nodes = _node_map()
        assert node_label(nodes["/members/alice"]) == "Alice"

    def test_falls_back_to_id(self) -> None:
        nodes = build_node_map({"items": [{"id": "only-id"}]})
        assert node_label(nodes["/items/only-id"]) == "only-id"

    def test_falls_back_to_anchor_path(self) -> None:
        # An array node carries none of title/name/id.
        nodes = _node_map()
        assert node_label(nodes["/members"]) == "/members"

    def test_mapping_without_title_name_id_falls_back_to_anchor_path(self) -> None:
        # A singleton mapping carrying none of the keys uses its path.
        nodes = build_node_map({"overview": {"foo": "bar"}})
        assert node_label(nodes["/overview"]) == "/overview"

    def test_missing_node_renders_its_path(self) -> None:
        assert node_label(MissingNode("/members/nobody")) == "/members/nobody"

    def test_missing_node_str_is_its_path(self) -> None:
        # `{{ node(...) }}` with no filter stringifies via __str__.
        assert str(MissingNode("/members/nobody")) == "/members/nobody"


# ── node_href ────────────────────────────────────────────────────


class TestNodeHref:
    def test_cross_page_relative_path_with_fragment(self) -> None:
        nodes = _node_map()
        source = nodes["/by_role/dev"]
        target = nodes["/members/alice"]
        assert node_href(_config(), source, target) == (
            "../members/alice.md#/members/alice"
        )

    def test_from_root_page(self) -> None:
        nodes = _node_map()
        source = nodes["/"]  # renders on index.md
        target = nodes["/members/alice"]
        assert node_href(_config(), source, target) == (
            "members/alice.md#/members/alice"
        )

    def test_same_page_self_link_keeps_filename(self) -> None:
        nodes = _node_map()
        node = nodes["/members/alice"]
        assert node_href(_config(), node, node) == "alice.md#/members/alice"

    def test_fragment_always_appended_even_for_page_root(self) -> None:
        nodes = _node_map()
        source = nodes["/"]
        target = nodes["/members/alice"]
        # alice is itself a page root, yet the fragment is not dropped.
        assert node_href(_config(), source, target).endswith("#/members/alice")
        # A MissingNode has no page/URL — the rendering filters handle that
        # (a broken reference is shown as plain text), so node_href is only
        # ever called for resolved nodes and carries no MissingNode branch.


# ── make_data_tree_filters (format-neutral, context-free) ─────────────


class TestMakeDataTreeFilters:
    """The context-free filters need no output format and no render context,
    so they live here rather than with a concrete format."""

    def test_returns_globals_and_filters(self) -> None:
        globals_map, filters_map = make_data_tree_filters(_node_map())
        assert set(globals_map) == {"node"}
        assert set(filters_map) == {"node", "label"}

    def test_node_filter_resolves_to_node(self) -> None:
        nodes = _node_map()
        _, filters_map = make_data_tree_filters(nodes)
        assert filters_map["node"]("members", "alice") is nodes["/members/alice"]

    def test_label_filter_selects_display_text(self) -> None:
        nodes = _node_map()
        _, filters_map = make_data_tree_filters(nodes)
        assert filters_map["label"](nodes["/members/alice"]) == "Alice"
