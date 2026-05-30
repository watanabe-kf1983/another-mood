# _parent / _parent_record / _meta are template-public fields, not Python-protected.
# pyright: reportPrivateUsage=false
"""Tests for ``data_tree`` — parent-reference wrappers and node metadata."""

import pytest

from another_mood.components.generator.data_tree import (
    ArrayNode,
    MappingNode,
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


class TestMetaAnchorId:
    """``_meta.anchor_id`` builds a ``/``-joined data-tree path per anchor-spec."""

    def test_root_is_empty(self) -> None:
        assert wrap_tree({})._meta.anchor_id == ""

    def test_singleton_mapping(self) -> None:
        root = wrap_tree({"overview": {"title": "T"}})
        assert root["overview"]._meta.anchor_id == "overview"

    def test_top_level_array(self) -> None:
        root = wrap_tree({"erds": []})
        assert root["erds"]._meta.anchor_id == "erds"

    def test_array_element_uses_id(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt"}]})
        assert root["erds"][0]._meta.anchor_id == "erds/user-mgmt"

    def test_nested_path(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entity = root["erds"][0]["entities"][0]
        assert entity._meta.anchor_id == "erds/user-mgmt/entities/user"

    def test_nested_array_segment(self) -> None:
        root = wrap_tree({"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]})
        entities = root["erds"][0]["entities"]
        assert entities._meta.anchor_id == "erds/user-mgmt/entities"

    def test_sibling_ids_in_different_arrays_do_not_collide(self) -> None:
        root = wrap_tree(
            {
                "erds": [
                    {"id": "user-mgmt", "entities": [{"id": "user"}]},
                    {"id": "order-flow", "entities": [{"id": "user"}]},
                ]
            }
        )
        a = root["erds"][0]["entities"][0]._meta.anchor_id
        b = root["erds"][1]["entities"][0]._meta.anchor_id
        assert a == "erds/user-mgmt/entities/user"
        assert b == "erds/order-flow/entities/user"
        assert a != b

    def test_slash_in_id_is_percent_encoded_outside_prose(self) -> None:
        root = wrap_tree({"items": [{"id": "a/b"}]})
        assert root["items"][0]._meta.anchor_id == "items/a%2Fb"

    def test_slash_in_id_is_kept_for_prose(self) -> None:
        root = wrap_tree({"prose": [{"id": "design/architecture"}]})
        assert root["prose"][0]._meta.anchor_id == "prose/design/architecture"

    def test_space_in_id_is_percent_encoded_even_in_prose(self) -> None:
        root = wrap_tree({"prose": [{"id": "design/with space"}]})
        assert root["prose"][0]._meta.anchor_id == "prose/design/with%20space"

    def test_hash_in_id_is_percent_encoded(self) -> None:
        root = wrap_tree({"items": [{"id": "a#b"}]})
        assert root["items"][0]._meta.anchor_id == "items/a%23b"

    def test_numeric_id_is_stringified(self) -> None:
        root = wrap_tree({"items": [{"id": 42}]})
        assert root["items"][0]._meta.anchor_id == "items/42"

    def test_result_is_cached(self) -> None:
        root = wrap_tree({"items": [{"id": "x"}]})
        meta = root["items"][0]._meta
        assert meta is root["items"][0]._meta


class TestMetaObjectTypeId:
    """``_meta.object_type_id`` mirrors the dotted ObjectType naming."""

    def test_root_is_empty(self) -> None:
        assert wrap_tree({})._meta.object_type_id == ""

    def test_singleton_mapping(self) -> None:
        root = wrap_tree({"overview": {}})
        assert root["overview"]._meta.object_type_id == "overview"

    def test_top_level_array(self) -> None:
        root = wrap_tree({"categories": []})
        assert root["categories"]._meta.object_type_id == "categories"

    def test_array_element_appends_item(self) -> None:
        root = wrap_tree({"categories": [{"id": "G"}]})
        assert root["categories"][0]._meta.object_type_id == "categories.item"

    def test_nested_array_path(self) -> None:
        root = wrap_tree({"categories": [{"id": "G", "tasks": []}]})
        tasks = root["categories"][0]["tasks"]
        assert tasks._meta.object_type_id == "categories.item.tasks"

    def test_nested_array_element_appends_item_again(self) -> None:
        root = wrap_tree({"categories": [{"id": "G", "tasks": [{"id": "G1"}]}]})
        task = root["categories"][0]["tasks"][0]
        assert task._meta.object_type_id == "categories.item.tasks.item"

    def test_singleton_under_singleton(self) -> None:
        root = wrap_tree({"meta": {"about": {}}})
        assert root["meta"]._meta.object_type_id == "meta"
        assert root["meta"]["about"]._meta.object_type_id == "meta.about"
