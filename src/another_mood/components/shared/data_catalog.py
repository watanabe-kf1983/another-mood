"""Catalog model — Node/Edge tree as canonical, Entity as flat serialization view.

Node carries the intrinsic body of a tree position; Edge is the parent's
view of that child.  Splitting them lets the composer detach a node and
re-wire it under a fresh Edge with new parent-side fields — heavily
relied on in query derivation.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, cast

# ── In-memory tree form (canonical) ───────────────────────────────────


@dataclass(frozen=True)
class XRef:
    """Foreign-key reference declared on a property via ``x-ref:``.

    ``entity`` is the target top-level entity id; ``attribute`` is the
    target attribute name.  The source-level shorthand of omitting
    ``attribute:`` (meaning "the synthetic ``.id`` of a dict-pattern
    target") is resolved at the SchemaTree → DataCatalog boundary, so
    on the catalog side ``attribute`` is always a real string.
    """

    entity: str
    attribute: str


@dataclass(frozen=True)
class Edge:
    """How a parent sees one of its children (the parent-side attribute view)."""

    name: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    x_ref: XRef | None = None


@dataclass(frozen=True)
class Node:
    metadata: Mapping[str, object] | None = None
    children: Sequence[tuple[Edge, "Node"]] = ()
    origin_item_type: str | None = None

    @property
    def is_entity(self) -> bool:
        """Whether this node materializes as an Entity in the flat catalog.

        Equivalent to having children: scalar nodes surface only as
        attributes on their parent and never become entities.
        """
        return bool(self.children)

    def has_child(self, name: str) -> bool:
        """Whether an edge named ``name`` exists among this node's children."""
        return any(e.name == name for e, _ in self.children)

    def require_child(self, name: str) -> None:
        """Raise :class:`UnknownChildError` if no child edge is named ``name``.

        For validate-only callers (e.g. clauses that re-emit the catalog
        unchanged) that want the same error vocabulary as ``child`` /
        ``child_entry`` without performing an access.
        """
        if not self.has_child(name):
            raise UnknownChildError(name)

    def child_entry(self, name: str) -> tuple[Edge, "Node"]:
        """Return the (edge, child) entry reached by the edge named ``name``.

        Raises :class:`UnknownChildError` if no such edge exists.
        """
        for e, c in self.children:
            if e.name == name:
                return e, c
        raise UnknownChildError(name)

    def child(self, name: str) -> "Node":
        """Return the child node reached by the edge named ``name``.

        Raises :class:`UnknownChildError` if no such edge exists.
        """
        return self.child_entry(name)[1]


class UnknownChildError(LookupError):
    """Raised by :meth:`Node.child` / :meth:`Node.child_entry` /
    :meth:`Node.require_child` when no child edge has the requested name.

    Carries ``name`` so callers (e.g. query derive) can re-raise their
    own typed error referencing the offending identifier.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


# ── Persistence form (serialization view) ─────────────────────────────


@dataclass(frozen=True)
class Attribute:
    id: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    child_entity: str | None = None  # child Entity.id (= access_path)
    child_item_type: str | None = None  # child ObjectType.id
    x_ref: XRef | None = None  # FK declaration from ``x-ref:``

    #: Node-form self-description of the persisted Attribute record.
    #: Composed into ``Entity.catalog`` as the child of the
    #: ``item_type.attributes`` edge.  The caller assigns the catalog id
    #: via ``flatten_tree(root_name=...)``; ``Attribute`` itself doesn't
    #: know where in the namespace it lives.
    #:
    #: ``XRef`` (the type of ``x_ref``) is singleton-flattened inline:
    #: the wrapper edge ``x_ref`` (type=object) plus dotted-name edges
    #: for each XRef field — mirroring the ``item_type.*`` flattening
    #: in ``Entity.catalog``.
    catalog: ClassVar[Node] = Node(
        children=[
            (Edge(name="id", type="string", required=True), Node()),
            (Edge(name="type", type="string", required=True), Node()),
            (Edge(name="required", type="boolean", required=True), Node()),
            (Edge(name="metadata", type="object", required=False), Node()),
            (Edge(name="validation", type="object", required=False), Node()),
            (Edge(name="child_entity", type="string", required=False), Node()),
            (Edge(name="child_item_type", type="string", required=False), Node()),
            (Edge(name="x_ref", type="object", required=False), Node()),
            (Edge(name="x_ref.entity", type="string", required=True), Node()),
            (Edge(name="x_ref.attribute", type="string", required=True), Node()),
        ],
    )

    def to_dict(self) -> Mapping[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Attribute":
        fields: dict[str, Any] = dict(d)
        x_ref_raw = fields.get("x_ref")
        if isinstance(x_ref_raw, Mapping):
            fields["x_ref"] = XRef(**cast(Mapping[str, Any], x_ref_raw))
        return cls(**fields)


@dataclass(frozen=True)
class ObjectType:
    id: str
    attributes: Sequence[Attribute]
    origin_item_type: str
    metadata: Mapping[str, object] | None = None

    def to_dict(self) -> Mapping[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ObjectType":
        return cls(
            **_without(d, "attributes", "origin_item_type"),
            origin_item_type=cast(str, d.get("origin_item_type") or d["id"]),
            attributes=[Attribute.from_dict(a) for a in d["attributes"]],
        )


@dataclass(frozen=True)
class Entity:
    id: str
    item_type: ObjectType
    parent_entity: str | None = None
    builtin: bool = False
    view: bool = False  # synthesized from a query (composer-set)

    #: Node-form self-description of the persisted Entity record.
    #: ``ObjectType`` (the type of ``item_type``) is singleton-flattened
    #: inline: the wrapper edge ``item_type`` (type=object) plus
    #: dotted-name edges ``item_type.id`` / ``item_type.origin_item_type``
    #: / ``item_type.metadata`` for scalars, and ``item_type.attributes``
    #: carrying ``Attribute.catalog`` as the child-entity link.
    #:
    #: The caller assigns the catalog id via
    #: ``flatten_tree(catalog, root_name=...)`` and is expected to set
    #: ``builtin=True`` before persisting.
    catalog: ClassVar[Node] = Node(
        children=[
            (Edge(name="id", type="string", required=True), Node()),
            (Edge(name="item_type", type="object", required=True), Node()),
            (Edge(name="item_type.id", type="string", required=True), Node()),
            (
                Edge(name="item_type.origin_item_type", type="string", required=True),
                Node(),
            ),
            (Edge(name="item_type.metadata", type="object", required=False), Node()),
            (
                Edge(name="item_type.attributes", type="object[]", required=True),
                Attribute.catalog,
            ),
            (Edge(name="parent_entity", type="string", required=False), Node()),
            (Edge(name="builtin", type="boolean", required=False), Node()),
            (Edge(name="view", type="boolean", required=False), Node()),
        ],
    )

    def to_dict(self) -> Mapping[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Entity":
        return cls(
            **_without(d, "item_type"),
            item_type=ObjectType.from_dict(d["item_type"]),
        )


# ── Conversion between forms ──────────────────────────────────────────


def build_tree(catalog: Sequence[Entity]) -> Node:
    """Build a virtual-root tree from a flat catalog list.

    The virtual root mirrors the records-side ``Sequence[Record]``
    wrapping that ``From.apply`` receives: every top-level entity hangs
    off it as an ``object[]`` edge so path traversal walks ``object[]``
    edges uniformly down to any leaf entity.
    """
    return Node(
        children=[
            (
                Edge(name=entity.id, type="object[]", required=True),
                _build_entity_node(entity, catalog),
            )
            for entity in _children_of(None, catalog)
        ],
    )


def flatten_tree(node: Node, root_name: str) -> Sequence[Entity]:
    """Flatten ``node`` into a list of Entity records.

    The top entity gets ``root_name`` as its id; descendant ids are
    built by joining the chain of child edge names with dots — the
    access_path convention shared by every catalog producer.
    """
    return _flatten_entity(node, edge_path=(root_name,), parent_entity_id=None)


# ── Internal helpers ──────────────────────────────────────────────────


def _without(d: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in keys}


def _build_entity_node(
    entity: Entity,
    catalog: Sequence[Entity],
) -> Node:
    """Build a Node body for ``entity`` (intrinsic fields only).

    ``entity.builtin`` is intentionally not carried into the tree: the
    catalog tree is a query-side intermediate, and a query view is never
    built-in by definition.  Composer marks query outputs as views after
    flattening; the built-in flag stays a flat-catalog concept.
    """
    sub_by_name = {
        e.id[len(entity.id) + 1 :]: e for e in _children_of(entity.id, catalog)
    }
    return Node(
        metadata=entity.item_type.metadata,
        children=[
            (
                _edge_from_attribute(attr),
                _build_entity_node(sub_by_name[attr.id], catalog)
                if attr.child_entity
                else Node(),
            )
            for attr in entity.item_type.attributes
        ],
        origin_item_type=entity.item_type.id,
    )


def _edge_from_attribute(attr: Attribute) -> Edge:
    """Build a Edge from a parent's Attribute pointing at this child."""
    return Edge(
        name=attr.id,
        type=attr.type,
        required=attr.required,
        metadata=attr.metadata,
        validation=attr.validation,
        x_ref=attr.x_ref,
    )


def _children_of(parent_id: str | None, catalog: Sequence[Entity]) -> Sequence[Entity]:
    """Entities in ``catalog`` whose ``parent_entity`` equals ``parent_id``."""
    return [e for e in catalog if e.parent_entity == parent_id]


def _flatten_entity(
    node: Node,
    *,
    edge_path: Sequence[str],
    parent_entity_id: str | None,
) -> Sequence[Entity]:
    """Flatten ``node`` into a list of Entity (parent first, descendants after).

    Caller's precondition: ``node.is_entity`` is True.  Scalar children
    of ``node`` are filtered out before recursion, so this function is
    only ever invoked on composite nodes.

    ``edge_path`` carries the chain of edge names traversed from the
    root.  Keeping it as a tuple (rather than a dot-joined string)
    preserves edge boundaries when an edge name itself contains dots
    (e.g. ``hobby.pets`` from a singleton-object flattening).
    """
    self_id = ".".join(edge_path)
    self_entity = Entity(
        id=self_id,
        item_type=_to_object_type(node, edge_path=edge_path),
        parent_entity=parent_entity_id,
    )
    descendants = [
        descendant
        for edge, child in node.children
        if child.is_entity
        for descendant in _flatten_entity(
            child,
            edge_path=(*edge_path, edge.name),
            parent_entity_id=self_id,
        )
    ]
    return [self_entity, *descendants]


def _to_object_type(node: Node, *, edge_path: Sequence[str]) -> ObjectType:
    """Build an ObjectType for ``node`` reached at ``edge_path``."""
    item_type_id = _item_type_id(edge_path)
    return ObjectType(
        id=item_type_id,
        attributes=[
            _to_attribute(child, edge=edge, edge_path=(*edge_path, edge.name))
            for edge, child in node.children
        ],
        origin_item_type=node.origin_item_type or item_type_id,
        metadata=node.metadata,
    )


def _to_attribute(node: Node, *, edge: Edge, edge_path: Sequence[str]) -> Attribute:
    """Build an Attribute for the (edge → node) connection at ``edge_path``."""
    return Attribute(
        id=edge.name,
        type=edge.type,
        required=edge.required,
        metadata=edge.metadata,
        validation=edge.validation,
        child_entity=".".join(edge_path) if node.is_entity else None,
        child_item_type=_item_type_id(edge_path) if node.is_entity else None,
        x_ref=edge.x_ref,
    )


def _item_type_id(edge_path: Sequence[str]) -> str:
    """Compute the ObjectType id for an entity reached via ``edge_path``.

    Joins edge names with ``.item.`` and appends a trailing ``.item``
    to match the recursive ``{...}.{name}.item`` ObjectType-id
    convention.  Dots inside a single edge name are preserved.
    """
    return ".item.".join(edge_path) + ".item"
