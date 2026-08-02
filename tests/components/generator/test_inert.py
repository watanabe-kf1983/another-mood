# `_meta` is a template-public reserved `_` field, not Python-protected.
# pyright: reportPrivateUsage=false
"""Tests for the inert value model — the marshal boundary."""

import pytest

from another_mood.components.generator.data_tree import (
    MappingNode,
    build_node_map,
)
from another_mood.components.generator.inert import (
    InertArray,
    InertMapping,
    ensure_inert,
    ensure_inert_array,
    ensure_inert_mapping,
)


class TestEnsureInert:
    """The general boundary: scalar pass, foreign-leaf raise, and identity of
    an already-inert value (so anchoring survives)."""

    def test_scalar_passes(self) -> None:
        assert ensure_inert(3) == 3

    def test_foreign_leaf_type_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_inert(object())

    def test_foreign_leaf_in_subtree_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_inert({"items": [{"text": object()}]})

    def test_anchored_node_passes_through_keeping_its_anchor(self) -> None:
        # Re-marshaling must return the node unchanged — repacking would strip
        # its anchor (`_parent` / `_meta`) and break `href` / `link`.
        node = build_node_map(ensure_inert_mapping({"members": [{"id": "alice"}]}))[
            "/members/alice"
        ]
        assert isinstance(node, MappingNode)
        assert ensure_inert(node) is node
        assert node._meta.anchor_path == "/members/alice"


class TestMutatorsSealed:
    """The containers are read-only after construction: the engine's wrap-side
    exposure makes every non-``_`` method template-callable, so a working
    mutator would let one page's template edit the tree shared by all pages.
    Each raises explicitly — never a silent no-op — and leaves the container
    intact."""

    @pytest.mark.parametrize(
        ("method", "args"),
        [
            ("clear", ()),
            ("pop", ("k",)),
            ("popitem", ()),
            ("setdefault", ("new", 1)),
            ("update", ({"k": 2},)),
        ],
        ids=lambda p: p if isinstance(p, str) else "",
    )
    def test_mapping_mutator_raises(self, method: str, args: tuple[object]) -> None:
        data = ensure_inert_mapping({"k": "v"})
        with pytest.raises(TypeError, match="read-only"):
            getattr(data, method)(*args)
        assert data == {"k": "v"}

    @pytest.mark.parametrize(
        ("method", "args"),
        [
            ("append", (3,)),
            ("clear", ()),
            ("extend", ([3],)),
            ("insert", (0, 3)),
            ("pop", ()),
            ("remove", (1,)),
            ("reverse", ()),
            ("sort", ()),
        ],
        ids=lambda p: p if isinstance(p, str) else "",
    )
    def test_array_mutator_raises(self, method: str, args: tuple[object]) -> None:
        items = ensure_inert_array([2, 1])
        with pytest.raises(TypeError, match="read-only"):
            getattr(items, method)(*args)
        assert items == [2, 1]


class TestEnsureInertMapping:
    """The mapping entry: repack a raw dict, return an already-inert mapping
    unchanged."""

    def test_repacks_raw_dict(self) -> None:
        result = ensure_inert_mapping({"items": [1, "a"]})
        assert isinstance(result, InertMapping)
        assert isinstance(result["items"], InertArray)

    def test_already_inert_returned_by_identity(self) -> None:
        inert = ensure_inert_mapping({"k": "v"})
        assert ensure_inert_mapping(inert) is inert


class TestEnsureInertArray:
    """The list entry: repack a raw list, return an already-inert array
    unchanged."""

    def test_repacks_raw_list(self) -> None:
        result = ensure_inert_array([{"k": "v"}, 1])
        assert isinstance(result, InertArray)
        assert isinstance(result[0], InertMapping)

    def test_already_inert_returned_by_identity(self) -> None:
        inert = ensure_inert_array([1, 2])
        assert ensure_inert_array(inert) is inert
