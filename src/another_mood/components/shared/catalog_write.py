"""Catalog writes — where a view clause's branches land in the output
catalog and what its removals take away, the counterpart of
``json_data_model.put`` and ``drop`` on the record side.  ``dc.Node``
stays read-only; these are functions over it.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.json_data_model import KeyPath


@dataclass(frozen=True)
class Placement:
    """A branch, the path it lands at, and its ``source``: the read-side
    path a row holds exactly when it holds the branch.  ``()`` for every
    row; one segment ``[]`` past an array edge for the rows holding an
    element of it."""

    branch: dc.Branch
    path: KeyPath
    source: KeyPath


def overlaps(a: KeyPath, b: KeyPath) -> bool:
    """Whether two write paths take the same place: one is the other or
    leads into it.  Segment-wise: ``hobby`` and ``hobbyist`` do not."""
    shorter = min(len(a), len(b))
    return a[:shorter] == b[:shorter]


def names(node: dc.Node) -> Iterator[KeyPath]:
    """The paths a row of ``node`` holds a value at, an array taken whole
    and an object on the way not a name of its own."""
    for edge, child in node.children:
        # Transitional: an edge name can still be a literal dotted key
        # from an upstream alias.  Read as the path it will be.
        head = tuple(edge.name.split("."))
        if edge.is_collection or not child.children:
            yield head
        else:
            yield from ((*head, *rest) for rest in names(child))


def remove(node: dc.Node, path: KeyPath) -> dc.Node:
    """``node`` without the branch at ``path``.  An object left with no
    children goes with it, up the chain: a row has no key for an
    absent value, so an object with nothing in it is on no row.  A
    path that is not there is a no-op."""
    head, rest = path[0], path[1:]
    if not node.has_child(head):
        return node
    if not rest:
        return _without_child(node, head)
    edge, child = node.child_entry(head)
    pruned = remove(child, rest)
    if pruned.children:
        return swap(node, (head,), (edge, pruned))
    else:
        return _without_child(node, head)


def require(node: dc.Node, path: KeyPath) -> dc.Node:
    """``node`` with every edge on the way to ``path`` required: what a
    clause says when it drops the rows that lack the path."""
    if not path:
        return node
    head, rest = path[0], path[1:]
    return replace(
        node,
        children=[
            (replace(edge, required=True), require(child, rest))
            if edge.name == head
            else (edge, child)
            for edge, child in node.children
        ],
    )


def swap(node: dc.Node, path: KeyPath, branch: dc.Branch) -> dc.Node:
    """``node`` with ``branch`` in the slot of the branch at ``path``:
    the holder keeps its other children where they were, and stays as
    declared even when the branch was all it held."""
    head, rest = path[0], path[1:]
    edge, child = node.child_entry(head)
    landed = (edge, swap(child, rest, branch)) if rest else branch
    return replace(
        node,
        children=[landed if e.name == head else (e, c) for e, c in node.children],
    )


def place(node: dc.Node, placements: Sequence[Placement]) -> dc.Node:
    """``node`` with each branch at its path: objects on the way kept
    where the node has them, made up where not, new children last in
    the order first written to.  The paths must be clear of the node's
    :func:`names` (see :func:`overlaps`)."""
    # The node is the row itself, on every row.
    return _place(node, placements, at=(), holder_sources=[()])


def _place(
    node: dc.Node,
    placements: Sequence[Placement],
    *,
    at: KeyPath,
    holder_sources: Sequence[KeyPath],
) -> dc.Node:
    """``place`` below the root: ``at`` is the node's path from it, and
    ``holder_sources`` the sources of the rows holding the node."""
    heads = list(dict.fromkeys(p.path[0] for p in placements))

    def toward(head: str) -> Sequence[Placement]:
        return [p for p in placements if p.path[0] == head]

    # An object already there holds what it held, on the rows it was:
    # its holder's when required, its own path's when not.  The paths
    # go on under it, since one ending there would be a name it holds.
    kept = [
        (
            edge,
            _place(
                child,
                [replace(p, path=p.path[1:]) for p in toward(edge.name)],
                at=(*at, edge.name),
                holder_sources=holder_sources if edge.required else [(*at, edge.name)],
            ),
        )
        if edge.name in heads
        else (edge, child)
        for edge, child in node.children
    ]
    made = [
        _child(head, toward(head), at=at, holder_sources=holder_sources)
        for head in heads
        if not node.has_child(head)
    ]
    return replace(node, children=[*kept, *made])


def _child(
    name: str,
    placements: Sequence[Placement],
    *,
    at: KeyPath,
    holder_sources: Sequence[KeyPath],
) -> dc.Branch:
    """A child made up from the placements whose path starts with its
    name: the branch itself when one ends here, else an object."""
    sources = [p.source for p in placements]
    # The child is on the rows its placements are; it is required when
    # that covers every row the holder is on.  The catalog says no more
    # about rows than which paths they hold, so two unrelated sources
    # never cover a third between them.
    required = all(
        any(_rows_within(holder, source) for source in sources)
        for holder in holder_sources
    )
    if len(placements) == 1 and len(placements[0].path) == 1:
        edge, node = placements[0].branch
        return replace(edge, name=name, required=required), node
    else:
        # The path goes on under this name for every placement: one
        # that ended here would have overlapped the others.
        return (
            dc.Edge(name=name, type="object", required=required),
            _place(
                dc.Node(),
                [replace(p, path=p.path[1:]) for p in placements],
                at=(*at, name),
                holder_sources=sources,
            ),
        )


def _without_child(node: dc.Node, name: str) -> dc.Node:
    return replace(node, children=[(e, c) for e, c in node.children if e.name != name])


def _rows_within(a: KeyPath, b: KeyPath) -> bool:
    """Whether every row holding source path ``a`` holds ``b``: ``b`` is
    a prefix of ``a``, the root ``()`` being a prefix of everything."""
    return a[: len(b)] == b
