# _parent / _parent_record are template-public fields, not Python-protected.
# pyright: reportPrivateUsage=false
"""Tests for ``data_tree`` — parent-reference wrappers and tree walker."""

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

    def test_nested_array_is_wrapped(self) -> None:
        root = wrap_tree({"grid": [[1, 2]]})
        assert isinstance(root["grid"][0], ArrayNode)

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

    def test_nested_array_parent_is_outer_array(self) -> None:
        root = wrap_tree({"grid": [[1, 2]]})
        assert root["grid"][0]._parent is root["grid"]


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

    def test_walks_through_nested_arrays(self) -> None:
        root = wrap_tree({"groups": [[{"id": "x"}]]})
        record = root["groups"][0][0]
        assert isinstance(record, MappingNode)
        assert record._parent_record is root


class TestSurface:
    """Wrapper attributes must not leak into the dict / list surface."""

    def test_parent_is_not_a_dict_key(self) -> None:
        root = wrap_tree({"a": 1})
        assert "_parent" not in root
        assert "_parent_record" not in root

    def test_mapping_node_behaves_as_dict(self) -> None:
        node = wrap_tree({"a": 1, "b": 2})
        assert dict(node) == {"a": 1, "b": 2}
        assert set(node.keys()) == {"a", "b"}
        assert sorted(node.items()) == [("a", 1), ("b", 2)]
