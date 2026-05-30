# _parent / _parent_record / _meta are template-public fields under the
# reserved `_` prefix, not Python "protected" attributes.
# pyright: reportPrivateUsage=false
"""Data-tree wrappers exposing parent references and node metadata to templates."""

from collections.abc import Iterable, Mapping
from functools import cached_property
from typing import Any, Protocol, cast
from urllib.parse import quote


class Node(Protocol):
    """An anchorable data-tree node that links back to its container."""

    _parent: "Node | None"
    """Reference to the container node, or ``None`` at the root."""

    _segment: str
    """How the parent reaches this node — used as a path segment in IDs.

    For Mappings/Arrays under a Mapping it is the dict key; for Mapping
    elements of an Array it is the element's ``id`` field value.  Empty
    at the root (never composed since ``_parent`` is ``None`` there).
    """

    _meta: "_NodeMeta"
    """Lazy node-metadata view — anchor_id / object_type_id."""


class ArrayNode(list[Any], Node):
    """List subclass holding a ``_parent`` reference to its container."""

    def __init__(self, items: Iterable[Any], *, parent: "Node", segment: str) -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent
        self._segment = segment
        self._meta: "_NodeMeta" = _NodeMeta(self)


class MappingNode(dict[str, Any], Node):
    """Dict subclass holding ``_parent`` and a lazy ``_parent_record``.

    ``_parent_record`` returns the nearest ``MappingNode`` ancestor,
    skipping any intervening ``ArrayNode`` layers so that a list
    element resolves directly to the containing record.
    """

    def __init__(
        self, items: Mapping[str, Any], *, parent: "Node | None", segment: str
    ) -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent
        self._segment = segment
        self._meta: "_NodeMeta" = _NodeMeta(self)

    @property
    def _parent_record(self) -> "MappingNode | None":
        node = self._parent
        while isinstance(node, ArrayNode):
            node = node._parent
        return node if isinstance(node, MappingNode) else None


class _NodeMeta:
    """Lazy node-metadata view exposed under ``node._meta``.

    Each property composes its parent's value with this node's
    ``_segment``; results are cached so repeated access is O(1).
    """

    def __init__(self, node: Node) -> None:
        self._node = node

    @cached_property
    def anchor_id(self) -> str:
        """Anchor ID — `/`-joined data-tree path.

        Empty string at the root.  ``urllib.parse.quote`` escapes
        URL-fragment-unsafe characters; the ``prose`` entity is exempt
        from ``/`` escaping so that path-shaped prose IDs stay readable.
        """
        parent = self._node._parent
        if parent is None:
            return ""
        # ``prose.item`` keeps ``/`` in id values unencoded so the
        # path-shaped prose IDs stay readable.
        safe = "/" if self.object_type_id == "prose.item" else ""
        seg = quote(self._node._segment, safe=safe)
        parent_id = parent._meta.anchor_id
        return f"{parent_id}/{seg}" if parent_id else seg

    @cached_property
    def object_type_id(self) -> str:
        """Schema-position ID — dotted path with ``.item`` for array elements.

        Empty at the root.  Mirrors the ObjectType naming convention
        used by ``data_catalog`` (``X.item.yyy.item`` etc.).
        """
        parent = self._node._parent
        if parent is None:
            return ""
        # Schema position of an Array element is the constant ``item`` —
        # the element's ``id`` only matters for anchor identity.
        seg = "item" if isinstance(parent, ArrayNode) else self._node._segment
        parent_id = parent._meta.object_type_id
        return f"{parent_id}.{seg}" if parent_id else seg


def wrap_tree(data: Mapping[str, Any]) -> MappingNode:
    """Wrap ``data`` into a tree of :class:`MappingNode` / :class:`ArrayNode`.

    The root :class:`MappingNode` carries ``_parent = None`` and an
    empty ``_segment``.  Inside an Array, only Mapping elements with an
    ``id`` field are wrapped — the others have no anchor path and so
    do their subtrees, so they pass through raw.
    """
    return _wrap_mapping(data, parent=None, segment="")


def _wrap_mapping(
    source: Mapping[str, Any], *, parent: Node | None, segment: str
) -> MappingNode:
    node = MappingNode({}, parent=parent, segment=segment)
    for key, value in source.items():
        if isinstance(value, Mapping):
            node[key] = _wrap_mapping(
                cast(Mapping[str, Any], value), parent=node, segment=key
            )
        elif isinstance(value, list):
            node[key] = _wrap_array(
                cast(Iterable[Any], value), parent=node, segment=key
            )
        else:
            node[key] = value
    return node


def _wrap_array(source: Iterable[Any], *, parent: Node, segment: str) -> ArrayNode:
    node = ArrayNode([], parent=parent, segment=segment)
    for value in source:
        if isinstance(value, Mapping) and "id" in value:
            # Mapping element of an Array — anchor segment is its ``id``.
            mapping = cast(Mapping[str, Any], value)
            node.append(_wrap_mapping(mapping, parent=node, segment=str(mapping["id"])))
        else:
            # No anchor path reaches scalars, lists, or id-less Mappings
            # — leave them (and their subtrees) raw.
            node.append(value)
    return node
