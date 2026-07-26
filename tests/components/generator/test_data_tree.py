# _parent / _parent_record / _meta are template-public fields, not Python-protected.
# pyright: reportPrivateUsage=false
"""Tests for ``data_tree`` — parent-reference wrappers and node metadata."""

from collections.abc import Mapping
from typing import Any

import pytest

from another_mood.components.generator.data_tree import (
    ArrayNode,
    MappingNode,
    Node,
    build_node_map,
    child,
    iter_nodes,
    nearest_ancestor,
    wrap_tree,
)
from another_mood.components.generator.inert import (
    InertArray,
    InertMapping,
    ensure_inert,
)


def _wrap(data: Mapping[str, Any]) -> MappingNode:
    """Marshal a raw dict, then anchor it — the two-stage build under test."""
    return wrap_tree(ensure_inert(data))


def _at(root: object, *path: object) -> object:
    """Index a wrapped tree by keys / indices; the caller narrows the result."""
    current = root
    for seg in path:
        if isinstance(current, InertArray):
            assert isinstance(seg, int)
            current = current[seg]
        elif isinstance(current, InertMapping):
            assert isinstance(seg, str)
            current = current[seg]
        else:
            raise AssertionError(f"{current!r} is not indexable at {seg!r}")
    return current


def _n(root: object, *path: object) -> Node:
    """:func:`_at` to a wrapped node (``_meta`` / ``_parent`` target)."""
    value = _at(root, *path)
    assert isinstance(value, Node)
    return value


def _mn(root: object, *path: object) -> MappingNode:
    """:func:`_at` to a ``MappingNode`` (``_parent_record`` target)."""
    value = _at(root, *path)
    assert isinstance(value, MappingNode)
    return value


class TestWrapping:
    """Which containers anchor vs. repack anchor-lessly — no bare dict/list survives."""

    def test_root_is_mapping_node(self) -> None:
        assert isinstance(_wrap({}), MappingNode)

    def test_singleton_child_is_mapping_node(self) -> None:
        root = _wrap({"overview": {"title": "T"}})
        assert isinstance(root["overview"], MappingNode)

    def test_top_level_array_is_array_node(self) -> None:
        root = _wrap({"items": []})
        assert isinstance(_at(root, "items"), ArrayNode)

    def test_array_element_with_id_is_wrapped(self) -> None:
        root = _wrap({"items": [{"id": "x"}]})
        assert isinstance(_at(root, "items", 0), MappingNode)

    def test_nested_array_is_anchorless_inert_array(self) -> None:
        # Array-under-Array has no anchor path — an anchor-less InertArray.
        root = _wrap({"grid": [[1, 2]]})
        elem = _at(root, "grid", 0)
        assert isinstance(elem, InertArray)
        assert not isinstance(elem, ArrayNode)

    def test_mapping_under_nested_array_is_anchorless_inert(self) -> None:
        root = _wrap({"groups": [[{"id": "x"}]]})
        inner = _at(root, "groups", 0)
        assert isinstance(inner, InertArray)
        assert not isinstance(inner, ArrayNode)
        assert isinstance(inner[0], InertMapping)
        assert not isinstance(inner[0], MappingNode)

    def test_scalar_passes_through(self) -> None:
        root = _wrap({"n": 7})
        assert root["n"] == 7

    def test_array_element_without_id_is_anchorless_inert_mapping(self) -> None:
        root = _wrap({"items": [{"text": "no-id"}]})
        elem = _at(root, "items", 0)
        assert isinstance(elem, InertMapping)
        assert not isinstance(elem, MappingNode)

    def test_descendants_of_anchorless_element_stay_anchorless(self) -> None:
        root = _wrap({"items": [{"nested": {"id": "x"}, "inner": [{"id": "y"}]}]})
        elem = _at(root, "items", 0)
        assert isinstance(elem, InertMapping)
        assert isinstance(elem["nested"], InertMapping)
        assert not isinstance(elem["nested"], MappingNode)
        assert isinstance(elem["inner"], InertArray)
        assert not isinstance(elem["inner"], ArrayNode)

    @pytest.mark.parametrize("id_value", ["", 0, False])
    def test_falsy_id_still_anchors_array_element(self, id_value: object) -> None:
        root = _wrap({"items": [{"id": id_value}]})
        assert isinstance(_at(root, "items", 0), MappingNode)


class TestParent:
    """``_parent`` points at the immediate container."""

    def test_root_has_no_parent(self) -> None:
        assert _wrap({})._parent is None

    def test_singleton_parent_is_root(self) -> None:
        root = _wrap({"overview": {}})
        assert _n(root, "overview")._parent is root

    def test_top_level_array_parent_is_root(self) -> None:
        root = _wrap({"items": []})
        assert _n(root, "items")._parent is root

    def test_list_element_parent_is_enclosing_array(self) -> None:
        root = _wrap({"items": [{"id": "x"}]})
        assert _n(root, "items", 0)._parent is _at(root, "items")


class TestParentRecord:
    """``_parent_record`` skips intervening ``ArrayNode`` layers."""

    def test_root_has_no_parent_record(self) -> None:
        assert _wrap({})._parent_record is None

    def test_singleton_equals_parent(self) -> None:
        root = _wrap({"overview": {}})
        overview = _mn(root, "overview")
        assert overview._parent_record is root
        assert overview._parent_record is overview._parent

    def test_list_element_skips_one_array(self) -> None:
        root = _wrap({"cats": [{"id": "G", "tasks": [{"id": "G1"}]}]})
        task = _mn(root, "cats", 0, "tasks", 0)
        assert task._parent_record is _at(root, "cats", 0)


class TestChild:
    """``child(node, seg)`` derives a node from its parent by anchor segment.

    (``_children`` is exercised through this and :class:`TestIterNodes`.)
    """

    def test_array_element_by_raw_id(self) -> None:
        # Matches the element's raw `id`, so a path-shaped id (with `/`)
        # resolves without escaping.
        root = _wrap({"prose": [{"id": "a/b"}]})
        assert child(_n(root, "prose"), "a/b") is _at(root, "prose", 0)

    def test_mapping_value_by_key(self) -> None:
        root = _wrap({"overview": {"title": "T"}})
        assert child(root, "overview") is _at(root, "overview")

    def test_no_match_is_none(self) -> None:
        root = _wrap({"items": [{"id": "x"}]})
        assert child(_n(root, "items"), "nope") is None


class TestSurface:
    """Wrapper attributes stay off the dict / list surface, and ``__slots__``
    bars new ones."""

    def test_parent_is_not_a_dict_key(self) -> None:
        root = _wrap({"a": 1})
        assert "_parent" not in root
        assert "_parent_record" not in root
        assert "_meta" not in root

    def test_node_rejects_arbitrary_attribute(self) -> None:
        root = _wrap({})
        with pytest.raises(AttributeError):
            # Deliberately illegal — __slots__ leaves no attribute to set.
            root.pub = object()  # pyright: ignore[reportAttributeAccessIssue]

    def test_mapping_node_behaves_as_dict(self) -> None:
        node = _wrap({"a": 1, "b": 2})
        assert dict(node) == {"a": 1, "b": 2}
        assert set(node.keys()) == {"a", "b"}
        assert sorted(node.items()) == [("a", 1), ("b", 2)]


class TestMetaAnchorPath:
    """``_meta.anchor_path`` builds an absolute ``/``-rooted data-tree path."""

    def test_root_is_slash(self) -> None:
        assert _wrap({})._meta.anchor_path == "/"

    def test_singleton_mapping(self) -> None:
        root = _wrap({"overview": {"title": "T"}})
        assert _n(root, "overview")._meta.anchor_path == "/overview"

    def test_top_level_array(self) -> None:
        root = _wrap({"erds": []})
        assert _n(root, "erds")._meta.anchor_path == "/erds"

    def test_array_element_uses_id(self) -> None:
        root = _wrap({"erds": [{"id": "user-mgmt"}]})
        assert _n(root, "erds", 0)._meta.anchor_path == "/erds/user-mgmt"

    def test_nested_path(self) -> None:
        root = _wrap({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entity = _n(root, "erds", 0, "entities", 0)
        assert entity._meta.anchor_path == "/erds/user-mgmt/entities/user"

    def test_nested_array_segment(self) -> None:
        root = _wrap({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entities = _n(root, "erds", 0, "entities")
        assert entities._meta.anchor_path == "/erds/user-mgmt/entities"

    def test_sibling_ids_in_different_arrays_do_not_collide(self) -> None:
        root = _wrap(
            {
                "erds": [
                    {"id": "user-mgmt", "entities": [{"id": "user"}]},
                    {"id": "order-flow", "entities": [{"id": "user"}]},
                ]
            }
        )
        a = _n(root, "erds", 0, "entities", 0)._meta.anchor_path
        b = _n(root, "erds", 1, "entities", 0)._meta.anchor_path
        assert a == "/erds/user-mgmt/entities/user"
        assert b == "/erds/order-flow/entities/user"
        assert a != b

    @pytest.mark.parametrize(
        ("collection", "id_value", "expected"),
        [
            # Default: the segment is IRI-escaped — reserved ASCII is
            # percent-encoded, ucschar stays raw, a non-str id is stringified.
            pytest.param("items", "a/b", "/items/a%2Fb", id="slash-escaped"),
            pytest.param("items", "a#b", "/items/a%23b", id="hash-escaped"),
            pytest.param("items", "書籍", "/items/書籍", id="ucschar-kept"),
            pytest.param("items", 42, "/items/42", id="numeric-stringified"),
            # prose/blob exception: their ids are contents-relative paths, so a
            # `/` stays raw.  Confined to those built-in collections — a user
            # entity (`items`, above) percent-encodes its `/`.
            pytest.param(
                "prose",
                "design/architecture",
                "/prose/design/architecture",
                id="slash-kept-prose",
            ),
            pytest.param(
                "blob",
                "covers/neon_after_rain.png",
                "/blob/covers/neon_after_rain.png",
                id="slash-kept-blob",
            ),
            # ...but only `/`; other reserved chars (a space) are still escaped.
            pytest.param(
                "prose",
                "design/with space",
                "/prose/design/with%20space",
                id="space-escaped-in-prose",
            ),
        ],
    )
    def test_segment_rendered_into_path(
        self, collection: str, id_value: object, expected: str
    ) -> None:
        node = _n(_wrap({collection: [{"id": id_value}]}), collection, 0)
        assert node._meta.anchor_path == expected

    def test_prose_heading_folds_headings_into_hash_fragment(self) -> None:
        # The `headings` segment folds onto the record's path as `#slug`; `#`
        # and the slug are raw, and the record keeps its `/`-exception.
        root = _wrap(
            {
                "prose": [
                    {"id": "design/architecture", "headings": [{"id": "エラー処理"}]}
                ]
            }
        )
        heading = _n(root, "prose", 0, "headings", 0)
        assert heading._meta.anchor_path == "/prose/design/architecture#エラー処理"

    def test_headings_fold_is_prose_specific(self) -> None:
        # With no catalog, an un-cataloged position falls back to itself, so a
        # same-named `headings` list under a non-prose entity keeps the generic
        # path (no `#` fold). Provenance-driven folding is TestMetaOriginItemType.
        root = _wrap({"other": [{"id": "x", "headings": [{"id": "h"}]}]})
        elem = _n(root, "other", 0, "headings", 0)
        assert elem._meta.anchor_path == "/other/x/headings/h"

    def test_result_is_cached(self) -> None:
        root = _wrap({"items": [{"id": "x"}]})
        meta = _n(root, "items", 0)._meta
        assert meta is _n(root, "items", 0)._meta


class TestMetaFragment:
    """``_meta.fragment`` is the URL fragment landing on the node — the
    anchor path whole, except a prose heading's bare native slug."""

    def test_data_node_fragment_is_its_anchor_path(self) -> None:
        root = _wrap({"members": [{"id": "alice"}]})
        assert _n(root, "members", 0)._meta.fragment == "/members/alice"

    def test_prose_heading_fragment_is_the_bare_slug(self) -> None:
        # The heading lands on the renderer's native id, so the fragment
        # is the slug alone — not the composed `/prose/…#slug` path.
        root = _wrap(
            {
                "prose": [
                    {"id": "design/architecture", "headings": [{"id": "エラー処理"}]}
                ]
            }
        )
        heading = _n(root, "prose", 0, "headings", 0)
        assert heading._meta.fragment == "エラー処理"


class TestMetaStampsAnchor:
    """``_meta.stamps_anchor`` — synthetic ids are stamped, a prose
    heading's native id is the renderer's."""

    def test_data_node_stamps(self) -> None:
        root = _wrap({"members": [{"id": "alice"}]})
        assert _n(root, "members", 0)._meta.stamps_anchor is True

    def test_prose_heading_does_not_stamp(self) -> None:
        root = _wrap(
            {"prose": [{"id": "design/architecture", "headings": [{"id": "h"}]}]}
        )
        heading = _n(root, "prose", 0, "headings", 0)
        assert heading._meta.stamps_anchor is False


class TestMetaObjectTypeId:
    """``_meta.object_type_id`` mirrors the dotted catalog naming —
    ``X.item`` for a record, ``X.item[]`` for the array of those records."""

    def test_root_is_item(self) -> None:
        # ``_item_type_id([])`` — the root object's type id.
        assert _wrap({})._meta.object_type_id == ".item"

    def test_singleton_mapping(self) -> None:
        root = _wrap({"overview": {}})
        assert _n(root, "overview")._meta.object_type_id == "overview"

    def test_top_level_array(self) -> None:
        root = _wrap({"categories": []})
        assert _n(root, "categories")._meta.object_type_id == "categories.item[]"

    def test_array_element_appends_item(self) -> None:
        root = _wrap({"categories": [{"id": "G"}]})
        assert _n(root, "categories", 0)._meta.object_type_id == "categories.item"

    def test_nested_array_path(self) -> None:
        root = _wrap({"categories": [{"id": "G", "tasks": []}]})
        tasks = _n(root, "categories", 0, "tasks")
        assert tasks._meta.object_type_id == "categories.item.tasks.item[]"

    def test_nested_array_element_appends_item_again(self) -> None:
        root = _wrap({"categories": [{"id": "G", "tasks": [{"id": "G1"}]}]})
        task = _n(root, "categories", 0, "tasks", 0)
        assert task._meta.object_type_id == "categories.item.tasks.item"

    def test_singleton_under_singleton(self) -> None:
        root = _wrap({"meta": {"about": {}}})
        assert _n(root, "meta")._meta.object_type_id == "meta"
        assert _n(root, "meta", "about")._meta.object_type_id == "meta.about"


class TestMetaOriginItemType:
    """``_meta.origin_item_type`` resolves a node's schema position to the
    entity its records derive from, so prose detection follows the type even
    when a query's ``flatten:`` / ``join:`` moves prose off its source
    position.  The id→origin map is read from ``__definition.entities``.
    """

    def test_uncataloged_position_falls_back_to_object_type_id(self) -> None:
        # No ``__definition`` to resolve through, so origin is the position id
        # itself — position-based detection still holds where no provenance is.
        node = _n(_wrap({"items": [{"id": "x"}]}), "items", 0)
        assert node._meta.origin_item_type == node._meta.object_type_id == "items.item"

    def test_prose_heading_detected_at_a_flattened_position(self) -> None:
        # A liner heading flattened into a view sits at a non-prose position
        # (`album_tracklist.item.liner.headings.item`), yet its catalog origin
        # is `prose.item.headings.item`, so detection fires there — the point
        # of B13.  Observed via the heading-only `#slug` fold it drives.
        data = {
            "__definition": {
                "entities": [
                    {
                        "item_type": {
                            "id": "album_tracklist.item.liner.headings.item",
                            "origin_item_type": "prose.item.headings.item",
                        }
                    }
                ]
            },
            "album_tracklist": [
                {"id": "tidal_atlas", "liner": {"headings": [{"id": "liner-notes"}]}}
            ],
        }
        heading = _n(_wrap(data), "album_tracklist", 0, "liner", "headings", 0)
        assert heading._meta.origin_item_type == "prose.item.headings.item"
        assert heading._meta.stamps_anchor is False
        assert heading._meta.anchor_path.endswith("#liner-notes")


class TestIterNodes:
    """``iter_nodes`` walks exactly the wrapped (anchorable) nodes."""

    def test_root_yielded_first(self) -> None:
        root = _wrap({"a": {}})
        assert next(iter(iter_nodes(root))) is root

    def test_visits_every_wrapped_node(self) -> None:
        root = _wrap({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        paths = {n._meta.anchor_path for n in iter_nodes(root)}
        assert paths == {
            "/",
            "/erds",
            "/erds/u",
            "/erds/u/entities",
            "/erds/u/entities/x",
        }

    def test_skips_idless_element_and_its_subtree(self) -> None:
        root = _wrap({"items": [{"text": "no-id", "child": {"id": "deep"}}]})
        paths = {n._meta.anchor_path for n in iter_nodes(root)}
        assert paths == {"/", "/items"}

    def test_skips_nested_array(self) -> None:
        root = _wrap({"grid": [[{"id": "x"}]]})
        paths = {n._meta.anchor_path for n in iter_nodes(root)}
        assert paths == {"/", "/grid"}


class TestBuildNodeMap:
    """``build_node_map`` keys each wrapped node by its own anchor_path.

    Which nodes are anchorable is ``iter_nodes``' contract (see
    :class:`TestIterNodes`); the anchor_path value — prose exception
    included — is ``_meta``'s (see :class:`TestMetaAnchorPath`).  Here we
    only pin what this function itself adds: the path-keyed index and the
    ``"/"`` root entry.
    """

    def test_each_node_keyed_by_its_anchor_path(self) -> None:
        nodes = build_node_map(
            ensure_inert({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        )
        for path, node in nodes.items():
            assert node._meta.anchor_path == path
        # The value is the identical wrapped node, reachable via the tree.
        u = nodes["/erds/u"]
        assert isinstance(u, MappingNode)
        assert nodes["/erds/u/entities/x"] is _at(u, "entities", 0)

    def test_root_is_the_slash_entry(self) -> None:
        nodes = build_node_map(ensure_inert({"overview": {}}))
        assert isinstance(nodes["/"], MappingNode)
        assert nodes["/"]._parent is None


class TestNearestAncestor:
    """``nearest_ancestor`` walks ``_parent`` up, ``self`` first."""

    def test_match_on_self_returns_self(self) -> None:
        root = _wrap({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        entity = _n(root, "erds", 0, "entities", 0)
        assert nearest_ancestor(entity, lambda _: True) is entity

    def test_returns_nearest_matching_ancestor(self) -> None:
        root = _wrap({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        entity = _n(root, "erds", 0, "entities", 0)

        def is_erd_element(n: Node) -> bool:
            return n._meta.object_type_id == "erds.item"

        assert nearest_ancestor(entity, is_erd_element) is _at(root, "erds", 0)

    def test_none_when_no_ancestor_matches(self) -> None:
        root = _wrap({"erds": [{"id": "u"}]})
        assert nearest_ancestor(_n(root, "erds", 0), lambda _: False) is None

    def test_root_matches_itself(self) -> None:
        root = _wrap({})
        assert nearest_ancestor(root, lambda n: n._parent is None) is root
