# _parent / _parent_record are template-public fields under the reserved
# `_` prefix, not Python "protected" attributes.
# pyright: reportPrivateUsage=false
"""Data-tree wrappers exposing parent references to templates."""

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, cast


class Node(Protocol):
    """An anchorable data-tree node that links back to its container."""

    _parent: "Node | None"
    """Reference to the container node, or ``None`` at the root.

    The leading underscore reserves a template-side namespace against
    user data keys (which by convention do not start with ``_``); it
    does *not* indicate Python-style protected access.  Treat this as
    a public field of the node API.
    """


class ArrayNode(list[Any], Node):
    """List subclass holding a ``_parent`` reference to its container."""

    def __init__(self, items: Iterable[Any], *, parent: "Node") -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent


class MappingNode(dict[str, Any], Node):
    """Dict subclass holding ``_parent`` and a lazy ``_parent_record``.

    ``_parent_record`` returns the nearest ``MappingNode`` ancestor,
    skipping any intervening ``ArrayNode`` layers so that a list
    element resolves directly to the containing record.
    """

    def __init__(self, items: Mapping[str, Any], *, parent: "Node | None") -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent

    @property
    def _parent_record(self) -> "MappingNode | None":
        node = self._parent
        while isinstance(node, ArrayNode):
            node = node._parent
        return node if isinstance(node, MappingNode) else None


def wrap_tree(data: Mapping[str, Any]) -> MappingNode:
    """Wrap ``data`` into a tree of :class:`MappingNode` / :class:`ArrayNode`.

    The root :class:`MappingNode` carries ``_parent = None``.  List
    elements without an ``id`` key are passed through unwrapped (and
    their subtrees are not visited), matching the anchor-spec rule
    that such elements lack an anchor ID and so their descendants
    have no reachable path either.
    """
    return _wrap_mapping(data, parent=None)


def _wrap_mapping(source: Mapping[str, Any], *, parent: Node | None) -> MappingNode:
    node = MappingNode({}, parent=parent)
    for key, value in source.items():
        node[key] = _wrap_value(value, parent=node)
    return node


def _wrap_array(source: Iterable[Any], *, parent: Node) -> ArrayNode:
    node = ArrayNode([], parent=parent)
    for value in source:
        if _is_unreachable_record(value):
            node.append(value)
        else:
            node.append(_wrap_value(value, parent=node))
    return node


def _is_unreachable_record(value: object) -> bool:
    """A list element that anchor-spec cannot reach.

    A Mapping without an ``id`` has no anchor path, and so neither do
    its descendants.  Such subtrees stay raw.
    """
    return isinstance(value, Mapping) and "id" not in value


def _wrap_value(value: object, *, parent: Node) -> object:
    if isinstance(value, Mapping):
        return _wrap_mapping(cast(Mapping[str, Any], value), parent=parent)
    if isinstance(value, list):
        return _wrap_array(cast(Iterable[Any], value), parent=parent)
    return value
