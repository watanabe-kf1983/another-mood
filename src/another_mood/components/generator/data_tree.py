# _parent / _parent_record / _meta / _children are template-public node
# fields under the reserved `_` prefix — reserved precisely so they never
# shadow a data key on the dict/list-subclass nodes — not Python
# "protected" attributes.
# pyright: reportPrivateUsage=false
"""Data-tree wrappers exposing parent references and node metadata to templates."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from functools import cached_property
from typing import Any, cast

from another_mood.components.generator.url import url_escape


class Node(ABC):
    """An anchorable data-tree node that links back to its container."""

    # Members are instance attributes set in ``__init__``, so they are
    # declared here as plain annotations, not ``@abstractmethod`` — the
    # latter would block subclasses from instantiating.
    _parent: "Node | None"
    """Reference to the container node, or ``None`` at the root."""

    _segment: str
    """How the parent reaches this node — used as a path segment in IDs.

    For Mappings/Arrays under a Mapping it is the dict key; for Mapping
    elements of an Array it is the element's ``id`` field value.  Empty
    at the root (never composed since ``_parent`` is ``None`` there).
    """

    _meta: "_NodeMeta"
    """Lazy node-metadata view — anchor_path / object_type_id."""

    @abstractmethod
    def _children(self) -> "Iterator[Node]":
        """The anchorable child nodes, in document order — the one
        container-shape-specific primitive that the free functions
        :func:`child` and :func:`iter_nodes` build on.
        """


class ArrayNode(list[Any], Node):
    """List subclass holding a ``_parent`` reference to its container."""

    def __init__(
        self,
        items: Iterable[Any],
        *,
        parent: "Node",
        segment: str,
        type_index: Mapping[str, str],
    ) -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent
        self._segment = segment
        self._meta: "_NodeMeta" = _NodeMeta(self, type_index)

    def _children(self) -> "Iterator[Node]":
        """The element nodes; id-less elements pass through raw and are skipped."""
        return (item for item in self if isinstance(item, Node))


class MappingNode(dict[str, Any], Node):
    """Dict subclass holding ``_parent`` and a lazy ``_parent_record``.

    ``_parent_record`` returns the nearest ``MappingNode`` ancestor,
    skipping any intervening ``ArrayNode`` layers so that a list
    element resolves directly to the containing record.
    """

    def __init__(
        self,
        items: Mapping[str, Any],
        *,
        parent: "Node | None",
        segment: str,
        type_index: Mapping[str, str],
    ) -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent
        self._segment = segment
        self._meta: "_NodeMeta" = _NodeMeta(self, type_index)

    @property
    def _parent_record(self) -> "MappingNode | None":
        node = self._parent
        while isinstance(node, ArrayNode):
            node = node._parent
        return node if isinstance(node, MappingNode) else None

    def _children(self) -> "Iterator[Node]":
        """The node-valued entries; raw scalar / pass-through values are skipped."""
        return (value for value in self.values() if isinstance(value, Node))


class _NodeMeta:
    """Lazy node-metadata view exposed under ``node._meta``."""

    def __init__(self, node: Node, type_index: Mapping[str, str]) -> None:
        self._node = node
        self._type_index = type_index

    @cached_property
    def anchor_path(self) -> str:
        """Anchor path — an absolute, ``/``-rooted path in the page's data
        tree.  The leading ``/`` marks it absolute, distinct from a
        relative reference.
        """
        return self._anchor.anchor_path(self._node)

    @cached_property
    def fragment(self) -> str:
        """URL fragment that lands on this node — what ``href`` appends.

        Usually the whole :attr:`anchor_path`; a bare slug for a prose
        heading (the renderer's native id), and empty for a blob, a file
        with no within-page landing.
        """
        return self._anchor.fragment(self._node)

    @cached_property
    def stamps_anchor(self) -> bool:
        """Whether the system emits an ``<a id>`` landing for this node.

        False for a prose heading: the markdown renderer emits the id
        natively, so a stamped ``<a id>`` would duplicate it.
        """
        return self._anchor.stamps_anchor()

    @cached_property
    def _anchor(self) -> "_Anchor":
        """The strategy that resolves this node's anchor (path / fragment /
        stamping)."""
        return _anchor_for(self.origin_item_type)

    @cached_property
    def origin_item_type(self) -> str:
        """The origin ObjectType id this node's records derive from."""
        return self._type_index.get(self.object_type_id, self.object_type_id)

    @cached_property
    def object_type_id(self) -> str:
        """Schema-position ID in catalog notation: a record/singleton node's
        dotted path (``X.item`` for an array element, ``X`` for a singleton),
        or an Array node's ``X.item[]`` — the array *of* that element type.
        """
        # The ``[]`` marker lives only on this public id; descendants compose
        # against the marker-less ``_type_path`` and so stay ``…item`` rather
        # than ``…item[].item``.
        path = self._type_path
        return f"{path}.item[]" if isinstance(self._node, ArrayNode) else path

    @cached_property
    def _type_path(self) -> str:
        """Dotted schema path, sans the array ``[]`` marker — the form
        descendants compose against.
        """
        parent = self._node._parent
        if parent is None:
            # Root: the empty edge path, whose type id is ``.item`` (the value
            # ``data_catalog._item_type_id`` yields there). Top-level entities
            # are catalog roots, so the root is deliberately not a prefix of
            # theirs — it contributes an empty prefix to descendants below.
            return ".item"
        # Schema position of an Array element is the constant ``item`` —
        # the element's ``id`` only matters for anchor identity.
        seg = "item" if isinstance(parent, ArrayNode) else self._node._segment
        parent_path = "" if parent._parent is None else parent._meta._type_path
        return f"{parent_path}.{seg}" if parent_path else seg


# --- Anchor strategies ------------------------------------------------------
#
# An ``_Anchor`` owns how a node's anchor is formed — its path, its URL
# fragment, and whether an ``<a id>`` is stamped.  ``_NodeMeta`` holds no
# anchor logic; it only selects the strategy (:attr:`_NodeMeta._anchor`) by
# origin type and delegates.
#
# This is the SEMANTIC axis of node metadata.  The STRUCTURAL axis (Array vs
# Mapping, feeding ``object_type_id`` / ``_type_path``) stays inline in
# ``_NodeMeta`` — it is already polymorphic in the node classes, so mixing it
# in here would double up an existing split.  And origin, the discriminant, is
# itself computed from that structural core, so these strategies ride on top
# of it rather than replacing ``_NodeMeta`` wholesale.


class _Anchor(ABC):
    """Strategy resolving a node's anchor: its path, fragment, and stamping."""

    @abstractmethod
    def anchor_path(self, node: Node) -> str:
        """Compose ``node``'s anchor path under this anchor."""

    @abstractmethod
    def fragment(self, node: Node) -> str:
        """The URL fragment that lands on ``node`` under this anchor."""

    @abstractmethod
    def stamps_anchor(self) -> bool:
        """Whether the system emits an ``<a id>`` landing for this anchor."""


class _SegmentAnchor(_Anchor):
    """A node anchored at the parent's path plus its own escaped segment.

    The default anchor for an ordinary data node (and the tree root, whose
    parentless base case ``anchor_path`` handles).  ``_ProseAnchor`` /
    ``_BlobAnchor`` refine it, differing only in :attr:`_raw_chars` and the
    fragment.
    """

    _raw_chars = ""

    def anchor_path(self, node: Node) -> str:
        parent = node._parent
        if parent is None:
            # The tree root — no parent to compose against.  The recursion's
            # base case, and the only node that reaches here parentless.
            return "/"
        seg = url_escape(node._segment, safe=self._raw_chars)
        parent_path = parent._meta.anchor_path
        # The root path already ends in ``/``; avoid doubling it.
        sep = "" if parent_path == "/" else "/"
        return f"{parent_path}{sep}{seg}"

    def fragment(self, node: Node) -> str:
        return self.anchor_path(node)

    def stamps_anchor(self) -> bool:
        return True


class _ProseAnchor(_SegmentAnchor):
    """A prose record — a contents-relative-path id that keeps ``/`` raw."""

    # Only the built-in prose/blob collections keep ``/`` raw, not every
    # ``/``-bearing id: a user entity's structure can change and reintroduce
    # ambiguity (anchor-spec.md#prose-の例外).
    _raw_chars = "/"


class _BlobAnchor(_SegmentAnchor):
    """A blob — a file node whose path-based id keeps ``/`` raw like a prose
    id, and which has no within-page landing, so its fragment is empty."""

    _raw_chars = "/"

    def fragment(self, node: Node) -> str:
        return ""


class _HeadingAnchor(_Anchor):
    """A prose heading — folds onto its record's path as ``#slug``.

    The markdown renderer emits the heading's id natively, so the fragment
    is the bare slug and nothing is stamped (a stamped ``<a id>`` would
    duplicate the native one).
    """

    def anchor_path(self, node: Node) -> str:
        record = cast(MappingNode, node)._parent_record
        assert record is not None  # a heading always has a record
        # ``#`` is a structural separator, and the github slug must match
        # the renderer's native heading id, so neither is escaped.
        return f"{record._meta.anchor_path}#{node._segment}"

    def fragment(self, node: Node) -> str:
        return node._segment

    def stamps_anchor(self) -> bool:
        return False


_DEFAULT_ANCHOR = _SegmentAnchor()
_ANCHOR_BY_ORIGIN: Mapping[str, _Anchor] = {
    "prose.item.headings.item": _HeadingAnchor(),
    "prose.item": _ProseAnchor(),
    "blob.item": _BlobAnchor(),
}


def _anchor_for(origin_item_type: str) -> _Anchor:
    """Select the anchor strategy for an ``origin_item_type`` (segment default)."""
    return _ANCHOR_BY_ORIGIN.get(origin_item_type, _DEFAULT_ANCHOR)


def wrap_tree(data: Mapping[str, Any]) -> MappingNode:
    """Wrap ``data`` into a tree of :class:`MappingNode` / :class:`ArrayNode`.

    The root :class:`MappingNode` carries ``_parent = None`` and an
    empty ``_segment``.  Inside an Array, only Mapping elements with an
    ``id`` field are wrapped — the others have no anchor path and so
    do their subtrees, so they pass through raw.
    """
    return _wrap_mapping(
        data, parent=None, segment="", type_index=_build_type_index(data)
    )


def build_node_map(data: Mapping[str, Any]) -> Mapping[str, Node]:
    """Index a wrapped data tree by anchor path in a single wrap pass.

    Maps each anchorable node's ``_meta.anchor_path`` to the node; the
    root is reachable as ``result["/"]``.  Only wrapped nodes appear —
    id-less Array elements and nested Arrays pass through raw (see
    :func:`wrap_tree`) and carry no anchor path.  Built on a flat
    full-path key so the prose/blob ``/``-keeping exception needs no
    special case here: each node's own ``anchor_path`` already encodes
    it.
    """
    return {node._meta.anchor_path: node for node in iter_nodes(wrap_tree(data))}


def iter_nodes(node: Node) -> Iterator[Node]:
    """Walk every wrapped node depth-first, ``node`` itself first.

    Descends via each node's :meth:`Node._children`, which already yields
    only anchorable :class:`Node` instances — raw pass-through dicts/lists
    (and their subtrees) are skipped without re-deriving any wrapping rule.
    """
    yield node
    for c in node._children():
        yield from iter_nodes(c)


def nearest_ancestor(node: Node, match: Callable[[Node], bool]) -> Node | None:
    """Nearest ``self``-or-ancestor satisfying ``match``, or ``None``.

    Ascending counterpart to :func:`iter_nodes`: walks ``_parent`` from
    ``node`` upward, returning the first node ``match`` accepts and
    ``None`` once it falls off past the root.
    """
    current: Node | None = node
    while current is not None:
        if match(current):
            return current
        current = current._parent
    return None


def is_blob(node: Node) -> bool:
    return node._meta.origin_item_type == "blob.item"


# A free function over the node tree, like :func:`iter_nodes` /
# :func:`nearest_ancestor`, rather than a method — so it cannot shadow a data
# key on the dict/list-subclass nodes.
def child(node: Node, seg: object) -> Node | None:
    """The child of ``node`` whose anchor segment equals ``seg``, or ``None``.

    ``seg`` is a record's ``id`` (array element) or a key (mapping entry) —
    both recorded on the child as ``_segment``, so a single match resolves
    either container kind, and a path-shaped id (a ``prose`` or ``blob``
    record) matches its raw value without escaping.
    """
    key = str(seg)
    return next((c for c in node._children() if c._segment == key), None)


def _build_type_index(data: Mapping[str, Any]) -> Mapping[str, str]:
    """Map each ObjectType id to its ``origin_item_type`` (empty without a catalog)."""
    entities = cast(
        Sequence[Mapping[str, Any]],
        data.get("__definition", {}).get("entities", []),
    )
    return {e["item_type"]["id"]: e["item_type"]["origin_item_type"] for e in entities}


def _wrap_mapping(
    source: Mapping[str, Any],
    *,
    parent: Node | None,
    segment: str,
    type_index: Mapping[str, str],
) -> MappingNode:
    node = MappingNode({}, parent=parent, segment=segment, type_index=type_index)
    for key, value in source.items():
        if isinstance(value, Mapping):
            node[key] = _wrap_mapping(
                cast(Mapping[str, Any], value),
                parent=node,
                segment=key,
                type_index=type_index,
            )
        elif isinstance(value, list):
            node[key] = _wrap_array(
                cast(Iterable[Any], value),
                parent=node,
                segment=key,
                type_index=type_index,
            )
        else:
            node[key] = value
    return node


def _wrap_array(
    source: Iterable[Any],
    *,
    parent: Node,
    segment: str,
    type_index: Mapping[str, str],
) -> ArrayNode:
    node = ArrayNode([], parent=parent, segment=segment, type_index=type_index)
    for value in source:
        if isinstance(value, Mapping) and "id" in value:
            # Mapping element of an Array — anchor segment is its ``id``.
            mapping = cast(Mapping[str, Any], value)
            node.append(
                _wrap_mapping(
                    mapping,
                    parent=node,
                    segment=str(mapping["id"]),
                    type_index=type_index,
                )
            )
        else:
            # No anchor path reaches scalars, lists, or id-less Mappings
            # — leave them (and their subtrees) raw.
            node.append(value)
    return node
