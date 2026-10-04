"""Tests for the catalog side of a view's writes.  ``place`` is covered
through ``Select.derive`` and ``Flatten.derive`` in ``test_query``,
whose expectations are the spec's examples."""

import pytest

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.catalog_write import names, overlaps

from .leaf_paths import tree


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
