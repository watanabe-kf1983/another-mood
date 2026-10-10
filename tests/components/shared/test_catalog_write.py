"""Tests for the catalog side of a view's writes.  The spec's examples
drive ``place`` through ``Select.derive`` and ``Flatten.derive`` in
``test_query``; here it is tested on its own, down to the shapes no
clause writes yet."""

import pytest

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.catalog_write import (
    Placement,
    names,
    overlaps,
    place,
    remove,
    require,
    swap,
)

from .leaf_paths import paths, tree


def write(branch: str, at: str, source: str = "") -> Placement:
    """A placement of ``branch`` (one leaf path; its root segment is the
    edge, renamed where it lands) bound for the dotted path ``at``, on
    the rows holding the dotted read path ``source``: every row when
    empty, the rows with an element when it ends in ``[]``."""
    [(edge, node)] = tree(branch).children
    return Placement(
        branch=(edge, node),
        path=tuple(at.split(".")),
        source=tuple(source.replace("[]", ".[]").split(".")) if source else (),
    )


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


class TestPlaceIntoAnEmptyRow:
    """What ``select`` does: every object on the way to a path is made up,
    on the rows its writes are on.  A made-up object is required when
    its writes cover every row of its holder, and a value inside it is
    required when the writes it merges with are all on rows that hold
    the value's own source."""

    @pytest.mark.parametrize(
        ("placements", "expected"),
        [
            pytest.param(
                [write("pets[].name", "owned")],
                "owned[].name",
                id="the branch comes whole, renamed",
            ),
            pytest.param(
                [write("v", "a.v", source="ref")],
                "a?.v",
                id="an object made up on some rows holds its one value",
            ),
            pytest.param(
                [write("pet", "pet", source="hobby.pets[]")],
                "pet?",
                id="an element is on the rows that have one",
            ),
            pytest.param(
                [write("p", "t.p", source="ref"), write("d", "t.d", source="ref")],
                "t?.p t?.d",
                id="two writes from the same rows",
            ),
            pytest.param(
                [write("p", "t.p", source="ref"), write("d", "t.d", source="ref.b")],
                "t?.p t?.d?",
                id="the narrower of two writes is optional",
            ),
            pytest.param(
                [write("p", "t.p", source="ref"), write("d", "t.d", source="x")],
                "t?.p? t?.d?",
                id="two unrelated writes are both optional",
            ),
            pytest.param(
                [write("v", "a.v"), write("w", "a.b.w", source="x")],
                "a.v a.b?.w",
                id="writes merging at different depths",
            ),
        ],
    )
    def test_shape(self, placements: list[Placement], expected: str) -> None:
        assert paths(place(dc.Node(), placements)) == expected


class TestPlaceIntoAnExistingRow:
    """What ``flatten`` does: the row keeps its other names, so a write
    can land beside them or inside an object already there.  Such an
    object is made up on the rows that get a write but lacked it, so
    its rows grow to the union; what it held before is then optional,
    and it is required once the union covers its holder."""

    @pytest.mark.parametrize(
        ("base", "placements", "expected"),
        [
            pytest.param(
                "id a.x",
                [write("v", "a.v", source="t[]")],
                "id a.x a.v?",
                id="an object on every row does not grow",
            ),
            pytest.param(
                "id a?.x",
                [write("v", "a.v", source="a")],
                "id a?.x a?.v",
                id="a write from inside the object does not grow it",
            ),
            pytest.param(
                "id a?.x a?.y?",
                [write("v", "a.v", source="a.y")],
                "id a?.x a?.y? a?.v?",
                id="a write from part of the object is optional in it",
            ),
            pytest.param(
                "id a?.x",
                [write("v", "a.v")],
                "id a.x? a.v",
                id="a write on every row puts the object on every row",
            ),
            pytest.param(
                "id a?.x",
                [write("v", "a.v", source="t[]")],
                "id a?.x? a?.v?",
                id="a write from unrelated rows grows the object",
            ),
            pytest.param(
                "id a?.b?.x",
                [write("v", "a.b.v")],
                "id a.b.x? a.b.v",
                id="growth goes down through nested objects",
            ),
            pytest.param(
                "id a?.b?.x a?.y",
                [write("v", "a.b.v", source="a")],
                "id a?.b.x? a?.b.v a?.y",
                id="growth stops at the object the write comes from",
            ),
            # The case no clause writes yet: two writes from different
            # rows merging into an object that was already there.  The
            # object is on the union of all three, so a value from one
            # write is optional unless the other two are on its rows.
            pytest.param(
                "a?.v a?.target?.q x?",
                [
                    write("v", "a.target.v", source="a"),
                    write("d", "a.target.d", source="x"),
                ],
                "a?.v? a?.target.q? a?.target.v? a?.target.d?",
                id="two writes merging into an object that was there",
            ),
        ],
    )
    def test_shape(self, base: str, placements: list[Placement], expected: str) -> None:
        assert paths(place(tree(base), placements)) == expected

    def test_keeps_the_object_as_declared(self) -> None:
        a_edge = dc.Edge(
            name="a", type="object", required=False, metadata={"title": "A"}
        )
        a = dc.Node(
            metadata={"title": "A object"},
            children=[(dc.Edge(name="x", type="string", required=True), dc.Node())],
        )
        out = place(dc.Node(children=[(a_edge, a)]), [write("v", "a.v")])
        grown, node = out.child_entry("a")
        assert grown == dc.Edge(
            name="a", type="object", required=True, metadata={"title": "A"}
        )
        assert node.metadata == a.metadata
        assert paths(out) == "a.x? a.v"
