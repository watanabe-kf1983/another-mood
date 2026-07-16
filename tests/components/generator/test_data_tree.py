# _parent / _parent_record / _meta are template-public fields, not Python-protected.
# pyright: reportPrivateUsage=false
"""Tests for ``data_tree`` — parent-reference wrappers and node metadata."""

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


class TestWrapping:
    """Which nodes get wrapped vs. passed through raw."""

    def test_root_is_mapping_node(self) -> None:
        assert isinstance(wrap_tree({}), MappingNode)

    def test_singleton_child_is_mapping_node(self) -> None:
        root = wrap_tree({"overview": {"title": "T"}})
        assert isinstance(root["overview"], MappingNode)

    def test_top_level_array_is_array_node(self) -> None:
        root = wrap_tree({"items": []})
        assert isinstance(root["items"], ArrayNode)

    def test_array_element_with_id_is_wrapped(self) -> None:
        root = wrap_tree({"items": [{"id": "x"}]})
        assert isinstance(root["items"][0], MappingNode)

    def test_nested_array_stays_raw(self) -> None:
        # Array-under-Array has no anchor path — leave it as a plain list
        # so every wrapped Node has a well-defined position in its parent.
        root = wrap_tree({"grid": [[1, 2]]})
        elem = root["grid"][0]
        assert isinstance(elem, list)
        assert not isinstance(elem, ArrayNode)

    def test_mapping_under_nested_array_stays_raw(self) -> None:
        root = wrap_tree({"groups": [[{"id": "x"}]]})
        inner = root["groups"][0]
        assert not isinstance(inner, ArrayNode)
        assert not isinstance(inner[0], MappingNode)

    def test_scalar_passes_through(self) -> None:
        root = wrap_tree({"n": 7})
        assert root["n"] == 7

    def test_array_element_without_id_is_raw(self) -> None:
        root = wrap_tree({"items": [{"text": "no-id"}]})
        elem = root["items"][0]
        assert isinstance(elem, dict)
        assert not isinstance(elem, MappingNode)

    def test_descendants_of_raw_element_stay_raw(self) -> None:
        root = wrap_tree({"items": [{"nested": {"id": "x"}, "inner": [{"id": "y"}]}]})
        elem = root["items"][0]
        assert not isinstance(elem["nested"], MappingNode)
        assert not isinstance(elem["inner"], ArrayNode)

    @pytest.mark.parametrize("id_value", ["", 0, False])
    def test_falsy_id_still_anchors_array_element(self, id_value: object) -> None:
        root = wrap_tree({"items": [{"id": id_value}]})
        assert isinstance(root["items"][0], MappingNode)


class TestParent:
    """``_parent`` points at the immediate container."""

    def test_root_has_no_parent(self) -> None:
        assert wrap_tree({})._parent is None

    def test_singleton_parent_is_root(self) -> None:
        root = wrap_tree({"overview": {}})
        assert root["overview"]._parent is root

    def test_top_level_array_parent_is_root(self) -> None:
        root = wrap_tree({"items": []})
        assert root["items"]._parent is root

    def test_list_element_parent_is_enclosing_array(self) -> None:
        root = wrap_tree({"items": [{"id": "x"}]})
        assert root["items"][0]._parent is root["items"]


class TestParentRecord:
    """``_parent_record`` skips intervening ``ArrayNode`` layers."""

    def test_root_has_no_parent_record(self) -> None:
        assert wrap_tree({})._parent_record is None

    def test_singleton_equals_parent(self) -> None:
        root = wrap_tree({"overview": {}})
        overview = root["overview"]
        assert isinstance(overview, MappingNode)
        assert overview._parent_record is root
        assert overview._parent_record is overview._parent

    def test_list_element_skips_one_array(self) -> None:
        root = wrap_tree({"cats": [{"id": "G", "tasks": [{"id": "G1"}]}]})
        task = root["cats"][0]["tasks"][0]
        assert isinstance(task, MappingNode)
        assert task._parent_record is root["cats"][0]


class TestChild:
    """``child(node, seg)`` derives a node from its parent by anchor segment.

    (``_children`` is exercised through this and :class:`TestIterNodes`.)
    """

    def test_array_element_by_raw_id(self) -> None:
        # Matches the element's raw `id`, so a path-shaped id (with `/`)
        # resolves without escaping.
        root = wrap_tree({"prose": [{"id": "a/b"}]})
        assert child(root["prose"], "a/b") is root["prose"][0]

    def test_mapping_value_by_key(self) -> None:
        root = wrap_tree({"overview": {"title": "T"}})
        assert child(root, "overview") is root["overview"]

    def test_no_match_is_none(self) -> None:
        root = wrap_tree({"items": [{"id": "x"}]})
        assert child(root["items"], "nope") is None


class TestSurface:
    """Wrapper attributes must not leak into the dict / list surface."""

    def test_parent_is_not_a_dict_key(self) -> None:
        root = wrap_tree({"a": 1})
        assert "_parent" not in root
        assert "_parent_record" not in root
        assert "_meta" not in root

    def test_mapping_node_behaves_as_dict(self) -> None:
        node = wrap_tree({"a": 1, "b": 2})
        assert dict(node) == {"a": 1, "b": 2}
        assert set(node.keys()) == {"a", "b"}
        assert sorted(node.items()) == [("a", 1), ("b", 2)]


class TestMetaAnchorPath:
    """``_meta.anchor_path`` builds an absolute ``/``-rooted data-tree path."""

    def test_root_is_slash(self) -> None:
        assert wrap_tree({})._meta.anchor_path == "/"

    def test_singleton_mapping(self) -> None:
        root = wrap_tree({"overview": {"title": "T"}})
        assert root["overview"]._meta.anchor_path == "/overview"

    def test_top_level_array(self) -> None:
        root = wrap_tree({"erds": []})
        assert root["erds"]._meta.anchor_path == "/erds"

    def test_array_element_uses_id(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt"}]})
        assert root["erds"][0]._meta.anchor_path == "/erds/user-mgmt"

    def test_nested_path(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entity = root["erds"][0]["entities"][0]
        assert entity._meta.anchor_path == "/erds/user-mgmt/entities/user"

    def test_nested_array_segment(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entities = root["erds"][0]["entities"]
        assert entities._meta.anchor_path == "/erds/user-mgmt/entities"

    def test_sibling_ids_in_different_arrays_do_not_collide(self) -> None:
        root = wrap_tree(
            {
                "erds": [
                    {"id": "user-mgmt", "entities": [{"id": "user"}]},
                    {"id": "order-flow", "entities": [{"id": "user"}]},
                ]
            }
        )
        a = root["erds"][0]["entities"][0]._meta.anchor_path
        b = root["erds"][1]["entities"][0]._meta.anchor_path
        assert a == "/erds/user-mgmt/entities/user"
        assert b == "/erds/order-flow/entities/user"
        assert a != b

    def test_slash_in_id_is_percent_encoded_for_user_entity(self) -> None:
        # The `/`-keeping exception is confined to the built-in prose/blob
        # collections; a user entity's `/`-bearing id is encoded.
        root = wrap_tree({"items": [{"id": "a/b"}]})
        assert root["items"][0]._meta.anchor_path == "/items/a%2Fb"

    def test_slash_in_id_is_kept_for_prose(self) -> None:
        root = wrap_tree({"prose": [{"id": "design/architecture"}]})
        assert root["prose"][0]._meta.anchor_path == "/prose/design/architecture"

    def test_slash_in_id_is_kept_for_blob(self) -> None:
        # A blob id is a contents-relative path like a prose id, so it shares
        # the exception — `covers/fig.png` stays raw, not `covers%2Ffig.png`.
        root = wrap_tree({"blob": [{"id": "covers/neon_after_rain.png"}]})
        expected = "/blob/covers/neon_after_rain.png"
        assert root["blob"][0]._meta.anchor_path == expected

    def test_space_in_id_is_percent_encoded_even_in_prose(self) -> None:
        root = wrap_tree({"prose": [{"id": "design/with space"}]})
        assert root["prose"][0]._meta.anchor_path == "/prose/design/with%20space"

    def test_prose_heading_folds_headings_into_hash_fragment(self) -> None:
        # The `headings` segment folds onto the record's path as `#slug`; `#`
        # and the slug are raw, and the record keeps its `/`-exception.
        root = wrap_tree(
            {
                "prose": [
                    {"id": "design/architecture", "headings": [{"id": "エラー処理"}]}
                ]
            }
        )
        heading = root["prose"][0]["headings"][0]
        assert heading._meta.anchor_path == "/prose/design/architecture#エラー処理"

    def test_headings_fold_is_prose_specific(self) -> None:
        # With no catalog, an un-cataloged position falls back to itself, so a
        # same-named `headings` list under a non-prose entity keeps the generic
        # path (no `#` fold). Provenance-driven folding is TestMetaOriginItemType.
        root = wrap_tree({"other": [{"id": "x", "headings": [{"id": "h"}]}]})
        elem = root["other"][0]["headings"][0]
        assert elem._meta.anchor_path == "/other/x/headings/h"

    def test_hash_in_id_is_percent_encoded(self) -> None:
        root = wrap_tree({"items": [{"id": "a#b"}]})
        assert root["items"][0]._meta.anchor_path == "/items/a%23b"

    def test_ucschar_in_id_is_kept_raw(self) -> None:
        # IRI form: non-ASCII ucschar pass through unencoded.
        root = wrap_tree({"items": [{"id": "書籍"}]})
        assert root["items"][0]._meta.anchor_path == "/items/書籍"

    def test_numeric_id_is_stringified(self) -> None:
        root = wrap_tree({"items": [{"id": 42}]})
        assert root["items"][0]._meta.anchor_path == "/items/42"

    def test_result_is_cached(self) -> None:
        root = wrap_tree({"items": [{"id": "x"}]})
        meta = root["items"][0]._meta
        assert meta is root["items"][0]._meta


class TestMetaFragment:
    """``_meta.fragment`` is the URL fragment landing on the node — the
    anchor path whole, except a prose heading's bare native slug."""

    def test_data_node_fragment_is_its_anchor_path(self) -> None:
        root = wrap_tree({"members": [{"id": "alice"}]})
        assert root["members"][0]._meta.fragment == "/members/alice"

    def test_prose_heading_fragment_is_the_bare_slug(self) -> None:
        # The heading lands on the renderer's native id, so the fragment
        # is the slug alone — not the composed `/prose/…#slug` path.
        root = wrap_tree(
            {
                "prose": [
                    {"id": "design/architecture", "headings": [{"id": "エラー処理"}]}
                ]
            }
        )
        heading = root["prose"][0]["headings"][0]
        assert heading._meta.fragment == "エラー処理"


class TestMetaStampsAnchor:
    """``_meta.stamps_anchor`` — synthetic ids are stamped, a prose
    heading's native id is the renderer's."""

    def test_data_node_stamps(self) -> None:
        root = wrap_tree({"members": [{"id": "alice"}]})
        assert root["members"][0]._meta.stamps_anchor is True

    def test_prose_heading_does_not_stamp(self) -> None:
        root = wrap_tree(
            {"prose": [{"id": "design/architecture", "headings": [{"id": "h"}]}]}
        )
        heading = root["prose"][0]["headings"][0]
        assert heading._meta.stamps_anchor is False


class TestMetaObjectTypeId:
    """``_meta.object_type_id`` mirrors the dotted catalog naming —
    ``X.item`` for a record, ``X.item[]`` for the array of those records."""

    def test_root_is_item(self) -> None:
        # ``_item_type_id([])`` — the root object's type id.
        assert wrap_tree({})._meta.object_type_id == ".item"

    def test_singleton_mapping(self) -> None:
        root = wrap_tree({"overview": {}})
        assert root["overview"]._meta.object_type_id == "overview"

    def test_top_level_array(self) -> None:
        root = wrap_tree({"categories": []})
        assert root["categories"]._meta.object_type_id == "categories.item[]"

    def test_array_element_appends_item(self) -> None:
        root = wrap_tree({"categories": [{"id": "G"}]})
        assert root["categories"][0]._meta.object_type_id == "categories.item"

    def test_nested_array_path(self) -> None:
        root = wrap_tree({"categories": [{"id": "G", "tasks": []}]})
        tasks = root["categories"][0]["tasks"]
        assert tasks._meta.object_type_id == "categories.item.tasks.item[]"

    def test_nested_array_element_appends_item_again(self) -> None:
        root = wrap_tree({"categories": [{"id": "G", "tasks": [{"id": "G1"}]}]})
        task = root["categories"][0]["tasks"][0]
        assert task._meta.object_type_id == "categories.item.tasks.item"

    def test_singleton_under_singleton(self) -> None:
        root = wrap_tree({"meta": {"about": {}}})
        assert root["meta"]._meta.object_type_id == "meta"
        assert root["meta"]["about"]._meta.object_type_id == "meta.about"


class TestMetaOriginItemType:
    """``_meta.origin_item_type`` resolves a node's schema position to the
    entity its records derive from, so prose detection follows the type even
    when a query's ``flatten:`` / ``join:`` moves prose off its source
    position.  The id→origin map is read from ``__definition.entities``.
    """

    def test_uncataloged_position_falls_back_to_object_type_id(self) -> None:
        # No ``__definition`` to resolve through, so origin is the position id
        # itself — position-based detection still holds where no provenance is.
        node = wrap_tree({"items": [{"id": "x"}]})["items"][0]
        assert node._meta.origin_item_type == node._meta.object_type_id == "items.item"

    def test_prose_heading_detected_at_a_flattened_position(self) -> None:
        # A liner heading flattened into a view sits at a non-prose position
        # (`album_tracklist.item.liner.headings.item`), yet its catalog origin
        # is `prose.item.headings.item`, so detection fires there — the point
        # of B13. The `#slug` fold this drives is TestMetaAnchorPath's concern.
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
        heading = wrap_tree(data)["album_tracklist"][0]["liner"]["headings"][0]
        assert heading._meta._is_prose_heading() is True


class TestIterNodes:
    """``iter_nodes`` walks exactly the wrapped (anchorable) nodes."""

    def test_root_yielded_first(self) -> None:
        root = wrap_tree({"a": {}})
        assert next(iter(iter_nodes(root))) is root

    def test_visits_every_wrapped_node(self) -> None:
        root = wrap_tree({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        paths = {n._meta.anchor_path for n in iter_nodes(root)}
        assert paths == {
            "/",
            "/erds",
            "/erds/u",
            "/erds/u/entities",
            "/erds/u/entities/x",
        }

    def test_skips_idless_element_and_its_subtree(self) -> None:
        root = wrap_tree({"items": [{"text": "no-id", "child": {"id": "deep"}}]})
        paths = {n._meta.anchor_path for n in iter_nodes(root)}
        assert paths == {"/", "/items"}

    def test_skips_nested_array(self) -> None:
        root = wrap_tree({"grid": [[{"id": "x"}]]})
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
        nodes = build_node_map({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        for path, node in nodes.items():
            assert node._meta.anchor_path == path
        # The value is the identical wrapped node, reachable via the tree.
        u = nodes["/erds/u"]
        assert isinstance(u, MappingNode)
        assert nodes["/erds/u/entities/x"] is u["entities"][0]

    def test_root_is_the_slash_entry(self) -> None:
        nodes = build_node_map({"overview": {}})
        assert isinstance(nodes["/"], MappingNode)
        assert nodes["/"]._parent is None


class TestNearestAncestor:
    """``nearest_ancestor`` walks ``_parent`` up, ``self`` first."""

    def test_match_on_self_returns_self(self) -> None:
        root = wrap_tree({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        entity = root["erds"][0]["entities"][0]
        assert nearest_ancestor(entity, lambda _: True) is entity

    def test_returns_nearest_matching_ancestor(self) -> None:
        root = wrap_tree({"erds": [{"id": "u", "entities": [{"id": "x"}]}]})
        entity = root["erds"][0]["entities"][0]

        def is_erd_element(n: Node) -> bool:
            return n._meta.object_type_id == "erds.item"

        assert nearest_ancestor(entity, is_erd_element) is root["erds"][0]

    def test_none_when_no_ancestor_matches(self) -> None:
        root = wrap_tree({"erds": [{"id": "u"}]})
        assert nearest_ancestor(root["erds"][0], lambda _: False) is None

    def test_root_matches_itself(self) -> None:
        root = wrap_tree({})
        assert nearest_ancestor(root, lambda n: n._parent is None) is root
