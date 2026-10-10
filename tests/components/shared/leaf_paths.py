"""A catalog tree written as its leaf paths, for tests that are about
the tree's shape.

One path per leaf, space-separated, outermost segment first.  A segment
is an edge name with ``[]`` for a collection and ``?`` for an optional
edge (absent on some rows that have its parent); an unmarked edge is
required.  So ``a.b?`` is an object ``a`` on every row holding a ``b``
that some rows lack, and ``arr[]?.x`` is an optional array of objects
each holding ``x``.  A segment with nothing under it is a string; one
with children is an object.

``tree`` builds a node from the notation and ``paths`` writes one back,
so an expected shape is a string next to the input it came from.
"""

from another_mood.components.shared import data_catalog as dc


def tree(text: str) -> dc.Node:
    return _branches([path.split(".") for path in text.split()])


def paths(node: dc.Node) -> str:
    return " ".join(_leaf_paths(node))


def _branches(paths: list[list[str]]) -> dc.Node:
    return dc.Node(
        children=[
            _branch(head, [p[1:] for p in paths if p[0] == head and p[1:]])
            for head in dict.fromkeys(p[0] for p in paths)
        ]
    )


def _branch(segment: str, tails: list[list[str]]) -> dc.Branch:
    node = _branches(tails) if tails else dc.Node()
    name = segment.removesuffix("?").removesuffix("[]")
    item = "object" if node.children else "string"
    return (
        dc.Edge(
            name=name,
            type=item + "[]" if "[]" in segment else item,
            required=not segment.endswith("?"),
        ),
        node,
    )


def _leaf_paths(node: dc.Node) -> list[str]:
    return [
        path
        for edge, child in node.children
        for segment in [
            edge.name
            + ("[]" if edge.is_collection else "")
            + ("?" * (not edge.required))
        ]
        for path in (
            [f"{segment}.{below}" for below in _leaf_paths(child)]
            if child.children
            else [segment]
        )
    ]
