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
    child,
    make_data_tree_filters,
    node_href,
    node_label,
    resolve_node,
)
from another_mood.components.generator.edition import Edition

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


def _edition() -> Edition:
    return Edition(file_per=_FILE_PER)


# ── build_anchor_path ──────────────────────────────────────────────


class TestBuildAnchorPath:
    """The segment part of an anchor path: each value escaped, `/`-prefixed
    and joined.  A verbatim ``path`` never reaches here — ``resolve_node``
    prepends it (see TestAnchorPathMode)."""

    def test_single_segment(self) -> None:
        assert build_anchor_path("overview") == "/overview"

    def test_multiple_segments(self) -> None:
        assert build_anchor_path("members", "alice") == "/members/alice"

    def test_segment_with_slash_is_escaped(self) -> None:
        # A `/` inside one built segment is percent-encoded — authors use
        # path= for path-shaped ids (prose), which is taken verbatim.
        assert build_anchor_path("prose", "a/b") == "/prose/a%2Fb"

    def test_non_string_segment_is_stringified(self) -> None:
        assert build_anchor_path("members", 7) == "/members/7"

    def test_no_segments_is_empty(self) -> None:
        # Contributes nothing without segments, so a verbatim path prefix
        # stands alone instead of gaining a trailing `/`.
        assert build_anchor_path() == ""


class TestAnchorPathMode:
    """Positional segments (each escaped) and a verbatim ``path=`` prefix are
    the two modes, surfaced at the call instead of inferred from a leading
    `/`; either alone works and the two compose."""

    def test_segments_and_path_reach_the_same_node(self) -> None:
        nodes = _node_map()
        built = resolve_node(nodes, "members", "alice")
        ready = resolve_node(nodes, path="/members/alice")
        assert built is ready is nodes["/members/alice"]

    def test_path_is_verbatim(self) -> None:
        # A prose id carries `/`; path= passes it through unescaped.
        nodes = _node_map()
        assert (
            resolve_node(nodes, path="/prose/design/architecture")
            is (nodes["/prose/design/architecture"])
        )

    def test_segments_escape_each_value(self) -> None:
        # The same path-shaped value as a positional segment is escaped, so
        # it does not reach the prose node.
        nodes = _node_map()
        assert resolve_node(nodes, "prose", "design/architecture") == MissingNode(
            "/prose/design%2Farchitecture"
        )

    def test_path_prefix_and_segments_compose(self) -> None:
        # path= is a verbatim prefix; positional segs dig into its children.
        nodes = _node_map()
        assert (
            resolve_node(nodes, "alice", path="/members") is (nodes["/members/alice"])
        )

    def test_leading_slash_positional_degrades_visibly(self) -> None:
        # A `/`-leading positional is a misuse, but it is not an error: it is
        # escaped (the `/` → `%2F`) and, not matching, shows as a MissingNode.
        nodes = _node_map()
        assert resolve_node(nodes, "/members/alice") == MissingNode(
            "/%2Fmembers%2Falice"
        )


# ── resolve_node ─────────────────────────────────────────────────


class TestResolveNode:
    def test_resolves_to_node(self) -> None:
        nodes = _node_map()
        assert resolve_node(nodes, "members", "alice") is (nodes["/members/alice"])

    def test_resolves_verbatim_prose_path(self) -> None:
        nodes = _node_map()
        assert (
            resolve_node(nodes, path="/prose/design/architecture")
            is (nodes["/prose/design/architecture"])
        )

    def test_missing_yields_missing_node(self) -> None:
        result = resolve_node(_node_map(), "members", "nobody")
        assert result == MissingNode("/members/nobody")

    def test_root_resolves(self) -> None:
        nodes = _node_map()
        assert resolve_node(nodes, path="/") is nodes["/"]


# ── child ────────────────────────────────────────────────────────


class TestChild:
    """The filter wraps ``data_tree.child``, turning a miss into a MissingNode.

    Resolution semantics are covered in ``test_data_tree.py``; these cover
    the adapter: a hit passes through, a miss/non-node becomes a MissingNode
    carrying the attempted path.
    """

    def test_resolves_to_node(self) -> None:
        nodes = _node_map()
        assert child(nodes["/members"], "alice") is nodes["/members/alice"]

    def test_missing_extends_parent_path(self) -> None:
        result = child(_node_map()["/members"], "nobody")
        assert result == MissingNode("/members/nobody")

    def test_missing_at_root_is_rooted(self) -> None:
        result = child(_node_map()["/"], "nope")
        assert result == MissingNode("/nope")

    def test_non_node_parent_yields_bare_segment(self) -> None:
        assert child("not a node", "x") == MissingNode("x")


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
        assert node_href(_edition(), source, target) == (
            "../members/alice.md#/members/alice"
        )

    def test_from_root_page(self) -> None:
        nodes = _node_map()
        source = nodes["/"]  # renders on index.md
        target = nodes["/members/alice"]
        assert node_href(_edition(), source, target) == (
            "members/alice.md#/members/alice"
        )

    def test_same_page_self_link_keeps_filename(self) -> None:
        nodes = _node_map()
        node = nodes["/members/alice"]
        assert node_href(_edition(), node, node) == "alice.md#/members/alice"

    def test_fragment_always_appended_even_for_page_root(self) -> None:
        nodes = _node_map()
        source = nodes["/"]
        target = nodes["/members/alice"]
        # alice is itself a page root, yet the fragment is not dropped.
        assert node_href(_edition(), source, target).endswith("#/members/alice")
        # A MissingNode has no page/URL — the rendering filters handle that
        # (a broken reference is shown as a bracketed `[text]`), so node_href is
        # only ever called for resolved nodes and carries no MissingNode branch.


# ── make_data_tree_filters (format-neutral, context-free) ─────────────


class TestMakeDataTreeFilters:
    """The context-free filters need no output format and no render context,
    so they live here rather than with a concrete format."""

    def test_returns_globals_and_filters(self) -> None:
        globals_map, filters_map = make_data_tree_filters(_node_map())
        assert set(globals_map) == {"node"}
        assert set(filters_map) == {"label", "child"}

    def test_node_global_resolves_segments(self) -> None:
        nodes = _node_map()
        globals_map, _ = make_data_tree_filters(nodes)
        assert globals_map["node"]("members", "alice") is nodes["/members/alice"]

    def test_node_global_resolves_path(self) -> None:
        nodes = _node_map()
        globals_map, _ = make_data_tree_filters(nodes)
        assert (
            globals_map["node"](path="/prose/design/architecture")
            is (nodes["/prose/design/architecture"])
        )

    def test_label_filter_selects_display_text(self) -> None:
        nodes = _node_map()
        _, filters_map = make_data_tree_filters(nodes)
        assert filters_map["label"](nodes["/members/alice"]) == "Alice"
