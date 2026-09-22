"""Catalog model — Node/Edge tree as canonical, Entity as flat serialization view.

Node carries the intrinsic body of a tree position; Edge is the parent's
view of that child.  Splitting them lets the composer detach a node and
re-wire it under a fresh Edge with new parent-side fields — heavily
relied on in query derivation.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import takewhile
from typing import Any, ClassVar, cast

# ── In-memory tree form (canonical) ───────────────────────────────────

type Branch = tuple[Edge, Node]

#: A node together with the chain of edges reaching it from an entity's
#: body.  A ``Branch`` is one step; this is the several steps a dotted
#: ``Attribute.id`` stands for, since singletons are folded into the
#: entity holding them.
type AttributeReach = tuple[Sequence[Edge], Node]


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

    #: Node-form self-description of the persisted record.  Assigned
    #: below, not here: ``Edge.x_ref`` puts ``XRef`` ahead of ``Node``.
    catalog: ClassVar["Node"]


@dataclass(frozen=True)
class Edge:
    """How a parent sees one of its children (the parent-side attribute view)."""

    name: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    x_ref: XRef | None = None

    @property
    def is_collection(self) -> bool:
        return self.type.endswith("[]")


@dataclass(frozen=True)
class Node:
    metadata: Mapping[str, object] | None = None
    children: Sequence[Branch] = ()
    origin_item_type: str | None = None

    # ── Child access by one edge name ─────────────────────────────────
    #
    # ``name`` is one edge name, never a path: a dot in it belongs to the
    # name, as in the top-level entity id ``__definition.entities``.

    def has_child(self, name: str) -> bool:
        return any(e.name == name for e, _ in self.children)

    def child_entry(self, name: str) -> Branch:
        """Raises :class:`UnknownChildError` if no child edge is named ``name``."""
        for e, c in self.children:
            if e.name == name:
                return e, c
        raise UnknownChildError(name)

    def child(self, name: str) -> "Node":
        """Raises :class:`UnknownChildError` if no child edge is named ``name``."""
        return self.child_entry(name)[1]

    # ── Child access by dotted path ───────────────────────────────────

    def descend(self, path: str) -> Branch:
        """Walk the dotted ``path``, traversing singleton objects only: a
        path may end on a collection attribute but never continue past one.

        Raises :class:`UnknownChildError` carrying the whole ``path``.
        """
        entry = self._descend(path)
        if entry is None:
            raise UnknownChildError(path)
        return entry

    def require_path(self, path: str) -> None:
        """Raises :class:`UnknownChildError` if ``path`` does not resolve."""
        self.descend(path)

    def _descend(self, path: str) -> Branch | None:
        name = self._longest_child_name(path)
        if name is None:
            return None
        edge, child = self.child_entry(name)
        if name == path:
            return edge, child
        if edge.is_collection:
            return None
        return child._descend(path[len(name) + 1 :])

    def _longest_child_name(self, path: str) -> str | None:
        # Longest-first, and the match commits — no backtracking — mirroring
        # how the data side resolves the same string against a record.
        # Transitional: view aliases (``select[].as``, ``flatten.as``,
        # ``join.as``, ``grouped.by``) become record keys verbatim, so an edge
        # name can still be a literal dotted key.  Once aliases are constrained
        # to paths, every dot means nesting and this is a plain split.
        candidate = path
        while not self.has_child(candidate):
            if "." not in candidate:
                return None
            candidate = candidate.rsplit(".", 1)[0]
        return candidate


XRef.catalog = Node(
    children=[
        (Edge(name="entity", type="string", required=True), Node()),
        (Edge(name="attribute", type="string", required=True), Node()),
    ],
)


def is_entity(edge: Edge, node: Node) -> bool:
    """Whether the ``edge`` → ``node`` link materializes as its own Entity.

    A singleton object has children too, but is inlined into the entity
    that holds it rather than becoming one.
    """
    return edge.is_collection and bool(node.children)


class UnknownChildError(LookupError):
    """Raised by the :class:`Node` accessors when a name or path does not
    resolve to a child edge.

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

    #: Node-form self-description of the persisted record.
    catalog: ClassVar[Node] = Node(
        children=[
            (Edge(name="id", type="string", required=True), Node()),
            (Edge(name="type", type="string", required=True), Node()),
            (Edge(name="required", type="boolean", required=True), Node()),
            (Edge(name="metadata", type="object", required=False), Node()),
            (Edge(name="validation", type="object", required=False), Node()),
            (Edge(name="child_entity", type="string", required=False), Node()),
            (Edge(name="child_item_type", type="string", required=False), Node()),
            (Edge(name="x_ref", type="object", required=False), XRef.catalog),
        ],
    )

    # ── Reading and writing the dotted id ─────────────────────────────
    #
    # ``id`` is one segment per edge, joined with dots: a singleton
    # object folds into the entity holding it rather than opening one of
    # its own.  These three are the only place spelling the separator.

    @staticmethod
    def join_id(names: Iterable[str]) -> str:
        return ".".join(names)

    def inlined_into(self, holder: "Attribute") -> bool:
        return self.id.startswith(f"{holder.id}.")

    def segment_under(self, holder: "Attribute | None") -> str:
        return self.id if holder is None else self.id[len(holder.id) + 1 :]

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

    #: Node-form self-description of the persisted record.
    catalog: ClassVar[Node] = Node(
        children=[
            (Edge(name="id", type="string", required=True), Node()),
            (Edge(name="origin_item_type", type="string", required=True), Node()),
            (Edge(name="metadata", type="object", required=False), Node()),
            (
                Edge(name="attributes", type="object[]", required=True),
                Attribute.catalog,
            ),
        ],
    )

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
    """One collection in the flat catalog, identified by its access path.

    A singleton object opens no entity of its own: it folds into the
    entity holding it, under dotted ``Attribute.id``.
    """

    id: str
    item_type: ObjectType
    parent_entity: str | None = None
    builtin: bool = False
    view: bool = False  # synthesized from a query (composer-set)

    #: Node-form self-description of the persisted record.  The caller
    #: assigns the catalog id via ``flatten_tree(catalog, root_name=...)``
    #: and is expected to set ``builtin=True`` before persisting.
    catalog: ClassVar[Node] = Node(
        children=[
            (Edge(name="id", type="string", required=True), Node()),
            (
                Edge(name="item_type", type="object", required=True),
                ObjectType.catalog,
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
    """Build a virtual-root tree from a flat catalog list — the inverse
    of :func:`flatten_tree`.

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
    """Flatten ``node`` into Entity records, the top one named ``root_name``."""
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
    sub_by_id = {
        e.id[len(entity.id) + 1 :]: e for e in _children_of(entity.id, catalog)
    }
    return Node(
        metadata=entity.item_type.metadata,
        children=_build_branches(
            entity.item_type.attributes,
            holder=None,
            sub_by_id=sub_by_id,
            catalog=catalog,
        ),
        origin_item_type=entity.item_type.id,
    )


def _build_branches(
    attributes: Sequence[Attribute],
    *,
    holder: Attribute | None,
    sub_by_id: Mapping[str, Entity],
    catalog: Sequence[Entity],
) -> Sequence[Branch]:
    """Restore one node's children from the attributes folded into it.

    ``holder`` is the singleton being restored, None at an entity's own body.
    """
    return [
        (
            _edge_from_attribute(attr, name=attr.segment_under(holder)),
            _build_attribute_node(attr, inlined, sub_by_id=sub_by_id, catalog=catalog),
        )
        for attr, inlined in _inlined_attributes(attributes)
    ]


def _inlined_attributes(
    attributes: Sequence[Attribute],
) -> Sequence[tuple[Attribute, Sequence[Attribute]]]:
    """Pair each attribute of one node with the attributes inlined into it.

    The inverse of ``_flatten_attributes``, whose emission order leaves
    the inlined attributes right after the ``object`` attribute whose id
    they extend.  A dotted id with no ``object`` attribute in front of it
    stays one edge name: a view alias becomes a record key verbatim.
    """
    if not attributes:
        return []
    head, rest = attributes[0], attributes[1:]
    inlined = (
        list(takewhile(lambda a: a.inlined_into(head), rest))
        if head.type == "object"
        else []
    )
    return [(head, inlined), *_inlined_attributes(rest[len(inlined) :])]


def _build_attribute_node(
    attr: Attribute,
    inlined: Sequence[Attribute],
    *,
    sub_by_id: Mapping[str, Entity],
    catalog: Sequence[Entity],
) -> Node:
    if attr.child_entity:
        return _build_entity_node(sub_by_id[attr.id], catalog)
    elif inlined:
        return Node(
            children=_build_branches(
                inlined,
                holder=attr,
                sub_by_id=sub_by_id,
                catalog=catalog,
            )
        )
    else:
        # ``Node()``, not an empty ``_build_branches``: ``children``
        # defaults to a tuple, and a list would not compare equal.
        return Node()


def _edge_from_attribute(attr: Attribute, *, name: str) -> Edge:
    """Build a Edge from a parent's Attribute pointing at this child."""
    return Edge(
        name=name,
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

    Caller's precondition: ``node`` is an entity node.  Children that do
    not open an entity of their own are filtered out before recursion,
    so this function is only ever invoked on composite nodes.

    ``edge_path`` stays a tuple rather than a dot-joined string because
    an attribute id can itself contain dots (``hobby.pets``).
    """
    self_id = ".".join(edge_path)
    attributes = _flatten_attributes(((), node))
    self_entity = Entity(
        id=self_id,
        item_type=_to_object_type(node, edge_path=edge_path, attributes=attributes),
        parent_entity=parent_entity_id,
    )
    descendants = [
        descendant
        for path, child in attributes
        if is_entity(path[-1], child)
        for descendant in _flatten_entity(
            child,
            edge_path=(*edge_path, _attribute_id(path)),
            parent_entity_id=self_id,
        )
    ]
    return [self_entity, *descendants]


def _flatten_attributes(reach: AttributeReach) -> Sequence[AttributeReach]:
    return [
        expanded
        for child in _inlined_children(reach)
        for expanded in [child, *_flatten_attributes(child)]
    ]


def _inlined_children(reach: AttributeReach) -> Sequence[AttributeReach]:
    path, node = reach
    # An entity's own body is reached by an empty chain: no edge to test,
    # and it always folds in.
    if not path or not path[-1].is_collection:
        return [((*path, edge), child) for edge, child in node.children]
    else:
        return []


def _attribute_id(path: Sequence[Edge]) -> str:
    return Attribute.join_id(edge.name for edge in path)


def _to_object_type(
    node: Node,
    *,
    edge_path: Sequence[str],
    attributes: Sequence[AttributeReach],
) -> ObjectType:
    """Build an ObjectType for ``node`` reached at ``edge_path``."""
    item_type_id = _item_type_id(edge_path)
    return ObjectType(
        id=item_type_id,
        attributes=[
            _to_attribute(
                child,
                edge=path[-1],
                edge_path=(*edge_path, _attribute_id(path)),
            )
            for path, child in attributes
        ],
        origin_item_type=node.origin_item_type or item_type_id,
        metadata=node.metadata,
    )


def _to_attribute(node: Node, *, edge: Edge, edge_path: Sequence[str]) -> Attribute:
    """Build an Attribute for the (edge → node) connection at ``edge_path``."""
    opens_entity = is_entity(edge, node)
    return Attribute(
        id=edge_path[-1],
        type=edge.type,
        required=edge.required,
        metadata=edge.metadata,
        validation=edge.validation,
        child_entity=".".join(edge_path) if opens_entity else None,
        child_item_type=_item_type_id(edge_path) if opens_entity else None,
        x_ref=edge.x_ref,
    )


def _item_type_id(edge_path: Sequence[str]) -> str:
    """Compute the ObjectType id for an entity reached via ``edge_path``.

    Joins path segments with ``.item.`` and appends a trailing ``.item``
    to match the recursive ``{...}.{name}.item`` ObjectType-id
    convention.  Dots inside a single segment are preserved.
    """
    return ".item.".join(edge_path) + ".item"
