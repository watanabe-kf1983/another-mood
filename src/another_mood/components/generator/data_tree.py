# _parent / _parent_record / _meta / _children are template-public node
# fields under the reserved `_` prefix — reserved precisely so they never
# shadow a data key on the dict/list-subclass nodes — not Python
# "protected" attributes.
# pyright: reportPrivateUsage=false
"""Data-tree wrappers exposing parent references and node metadata to templates."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from functools import cached_property
from typing import Any, cast

from another_mood.components.generator.url import url_escape


class Node(ABC):
    """An anchorable data-tree node that links back to its container.

    Its members are instance attributes set in ``__init__``, so they are
    declared here as annotations rather than ``@abstractmethod`` (which
    would block subclasses from instantiating).
    """

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

    def __init__(self, items: Iterable[Any], *, parent: "Node", segment: str) -> None:
        super().__init__(items)
        self._parent: "Node | None" = parent
        self._segment = segment
        self._meta: "_NodeMeta" = _NodeMeta(self)

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

    def _children(self) -> "Iterator[Node]":
        """The node-valued entries; raw scalar / pass-through values are skipped."""
        return (value for value in self.values() if isinstance(value, Node))


class _NodeMeta:
    """Lazy node-metadata view exposed under ``node._meta``.

    Each property composes its parent's value with this node's
    ``_segment``; results are cached so repeated access is O(1).
    """

    def __init__(self, node: Node) -> None:
        self._node = node

    @cached_property
    def anchor_path(self) -> str:
        """Anchor path — absolute, `/`-rooted data-tree path.

        ``/`` at the root; every other node is the parent's path plus
        its escaped segment.  The leading ``/`` marks the path as
        absolute within the page's data tree (distinct from a relative
        reference).  Each segment is IRI-escaped via ``url_escape``, save
        two ``prose`` exceptions: a prose record keeps ``/`` in its id
        unencoded so path-shaped ids stay readable, and a prose heading
        folds the ``headings`` segment into a ``#slug`` fragment.
        """
        parent = self._node._parent
        if parent is None:
            return "/"
        if self._is_prose_heading():
            record = cast(MappingNode, self._node)._parent_record
            assert record is not None  # a heading always has a record
            # ``#`` is a structural separator, and the github slug must
            # match the renderer's native heading id, so neither is escaped.
            return f"{record._meta.anchor_path}#{self._node._segment}"
        safe = "/" if self._is_prose_record() else ""
        seg = url_escape(self._node._segment, safe=safe)
        parent_path = parent._meta.anchor_path
        # The root path already ends in ``/``; avoid doubling it.
        sep = "" if parent_path == "/" else "/"
        return f"{parent_path}{sep}{seg}"

    @cached_property
    def fragment(self) -> str:
        """URL fragment that lands on this node — what ``href`` appends.

        Equivalent to "the part of :attr:`anchor_path` after the last
        ``#``", held as its own property so no consumer re-parses the
        composed path string.
        """
        if self._is_prose_heading():
            return self._node._segment
        else:
            return self.anchor_path

    @cached_property
    def stamps_anchor(self) -> bool:
        """Whether the system emits an ``<a id>`` landing for this node.

        False for a prose heading: the markdown renderer emits its id
        natively, so a stamped ``<a id>`` would duplicate it.
        """
        return not self._is_prose_heading()

    def _is_prose_record(self) -> bool:
        return self.object_type_id == "prose.item"

    def _is_prose_heading(self) -> bool:
        return self.object_type_id == "prose.item.headings.item"

    @cached_property
    def object_type_id(self) -> str:
        """Schema-position ID in catalog notation.

        A record/singleton node is its dotted path (``X.item`` for an
        array element, ``X`` for a singleton); an Array node is the
        catalog ``X.item[]`` form — the array *of* that element type. The
        ``[]`` marker is appended only here, on the public id, so an
        Array's descendants compose against the plain :attr:`_type_path`
        and stay ``…item`` rather than ``…item[].item``.
        """
        path = self._type_path
        return f"{path}.item[]" if isinstance(self._node, ArrayNode) else path

    @cached_property
    def _type_path(self) -> str:
        """Dotted schema path, sans array marker — composed by descendants.

        ``.item`` at the root — the value ``data_catalog._item_type_id``
        yields for the empty edge path, i.e. the root object's type.
        Top-level entities are catalog roots (``parent_entity=None``), so
        the root's id is deliberately not a prefix of theirs; the root
        contributes an empty prefix in the composition below.
        """
        parent = self._node._parent
        if parent is None:
            return ".item"
        # Schema position of an Array element is the constant ``item`` —
        # the element's ``id`` only matters for anchor identity.
        seg = "item" if isinstance(parent, ArrayNode) else self._node._segment
        parent_path = "" if parent._parent is None else parent._meta._type_path
        return f"{parent_path}.{seg}" if parent_path else seg


def wrap_tree(data: Mapping[str, Any]) -> MappingNode:
    """Wrap ``data`` into a tree of :class:`MappingNode` / :class:`ArrayNode`.

    The root :class:`MappingNode` carries ``_parent = None`` and an
    empty ``_segment``.  Inside an Array, only Mapping elements with an
    ``id`` field are wrapped — the others have no anchor path and so
    do their subtrees, so they pass through raw.
    """
    return _wrap_mapping(data, parent=None, segment="")


def build_node_map(data: Mapping[str, Any]) -> Mapping[str, Node]:
    """Index a wrapped data tree by anchor path in a single wrap pass.

    Maps each anchorable node's ``_meta.anchor_path`` to the node; the
    root is reachable as ``result["/"]``.  Only wrapped nodes appear —
    id-less Array elements and nested Arrays pass through raw (see
    :func:`wrap_tree`) and carry no anchor path.  Built on a flat
    full-path key so the ``prose`` ``/``-keeping exception needs no
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


def child(node: Node, seg: object) -> Node | None:
    """The child of ``node`` whose anchor segment equals ``seg``, or ``None``.

    ``seg`` is a record's ``id`` (array element) or a key (mapping entry) —
    both recorded on the child as ``_segment``, so a single match resolves
    either container kind, and a path-shaped id (e.g. a ``prose`` record)
    matches its raw value without escaping.  A free function over the node
    tree like :func:`iter_nodes` / :func:`nearest_ancestor`, rather than a
    method, so it cannot shadow a data key on the dict/list-subclass nodes.
    """
    key = str(seg)
    return next((c for c in node._children() if c._segment == key), None)


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
