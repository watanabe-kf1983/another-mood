"""Tests for the catalog side of a view's writes.  ``place`` is covered
through ``Select.derive`` and ``Flatten.derive`` in ``test_query``,
whose expectations are the spec's examples."""

import pytest

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.catalog_write import (
    names,
    overlaps,
    remove,
    require,
    swap,
)

from .leaf_paths import paths, tree


class TestOverlaps:
    """Two write paths overlap when one is the other or leads into it:
    writing a name claims everything under it."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (("a",), ("a",)),
            (("a",), ("a", "b")),
            (("a", "b"), ("a", "b", "c")),
        ],
        ids=["the same", "one leads into the other", "deeper down"],
    )
    def test_overlapping(self, a: tuple[str, ...], b: tuple[str, ...]) -> None:
        assert overlaps(a, b)
        assert overlaps(b, a)

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (("a",), ("b",)),
            (("a", "b"), ("a", "c")),
            (("a", "b", "c"), ("a", "x", "c")),
            (("hobby",), ("hobbyist",)),
        ],
        ids=["different names", "siblings", "parted above", "string prefix"],
    )
    def test_clear_of_each_other(self, a: tuple[str, ...], b: tuple[str, ...]) -> None:
        assert not overlaps(a, b)
        assert not overlaps(b, a)


class TestNames:
    """The names a row holds are the paths to its values.  An array is
    one name, nothing being written into it; an object on the way is
    not one, writes landing beside its children."""

    def test_paths_to_values_and_arrays(self) -> None:
        assert list(names(tree("id hobby.level hobby.pets[].name tags[]"))) == [
            ("id",),
            ("hobby", "level"),
            ("hobby", "pets"),
            ("tags",),
        ]

    def test_reads_a_literal_dotted_edge_name_as_a_path(self) -> None:
        # Transitional: an upstream alias can still land as one dotted key.
        node = dc.Node(
            children=[
                (dc.Edge(name="hobby.level", type="string", required=True), dc.Node())
            ]
        )
        assert list(names(node)) == [("hobby", "level")]


class TestRemove:
    """The counterpart of ``json_data_model.drop``: the branch goes, and
    an object it leaves empty goes with it up the chain."""

    @pytest.mark.parametrize(
        ("base", "path", "expected"),
        [
            ("a b c", ("b",), "a c"),
            ("id hobby.level hobby.pets[]", ("hobby", "pets"), "id hobby.level"),
            ("id hobby.pets[]", ("hobby", "pets"), "id"),
            ("id a.b.c", ("a", "b", "c"), "id"),
            ("id a.x a.b.c", ("a", "b", "c"), "id a.x"),
        ],
        ids=[
            "at the root",
            "nested",
            "empties the object",
            "empties two objects",
            "empties the inner object only",
        ],
    )
    def test_shape(self, base: str, path: tuple[str, ...], expected: str) -> None:
        assert paths(remove(tree(base), path)) == expected

    @pytest.mark.parametrize(
        "path", [("x",), ("a", "x")], ids=["at the root", "nested"]
    )
    def test_leaves_a_node_without_the_path_as_it_is(
        self, path: tuple[str, ...]
    ) -> None:
        node = tree("a.b c")
        assert remove(node, path) == node

    def test_keeps_the_rest_as_declared(self) -> None:
        edge = dc.Edge(name="a", type="object", required=False, metadata={"t": 1})
        node = dc.Node(
            metadata={"n": 1},
            children=[
                (edge, tree("b c")),
                (dc.Edge(name="z", type="string", required=True), dc.Node()),
            ],
        )
        out = remove(node, ("a", "b"))
        assert out.metadata == node.metadata
        assert [e for e, _ in out.children] == [edge, node.children[1][0]]
        assert paths(out) == "a?.c z"


class TestRequire:
    def test_marks_every_edge_on_the_way(self) -> None:
        assert paths(require(tree("a?.b?.c? a?.x? y?"), ("a", "b", "c"))) == (
            "a.b.c a.x? y?"
        )

    def test_takes_the_empty_path_as_the_row_itself(self) -> None:
        node = tree("a? b")
        assert require(node, ()) == node


class TestSwap:
    """The branch at the path is replaced in its slot; the holder is
    left as it is otherwise, emptied or not."""

    def test_keeps_the_slot(self) -> None:
        pet = (dc.Edge(name="pet", type="string", required=True), dc.Node())
        out = swap(tree("id hobby.a hobby.pets[] hobby.z"), ("hobby", "pets"), pet)
        assert paths(out) == "id hobby.a hobby.pet hobby.z"

    def test_keeps_the_holder_as_declared(self) -> None:
        hobby_edge = dc.Edge(
            name="hobby", type="object", required=True, metadata={"title": "Hobby"}
        )
        hobby = dc.Node(
            metadata={"title": "Hobby object"},
            children=[
                (dc.Edge(name="pets", type="string[]", required=True), dc.Node())
            ],
        )
        pet = (dc.Edge(name="pet", type="string", required=True), dc.Node())
        out = swap(dc.Node(children=[(hobby_edge, hobby)]), ("hobby", "pets"), pet)
        kept, node = out.child_entry("hobby")
        assert kept == hobby_edge
        assert node.metadata == hobby.metadata
        assert node.children == [pet]
