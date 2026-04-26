"""CatalogNode — in-memory tree representation of the data catalog.

Used as the input/output of every ``QueryNode.derive`` stage.  The tree
splits the persistence-layer dc.Entity / dc.ObjectType / dc.Attribute
into two roles:

* ``CatalogNode`` carries an entity's intrinsic body — its own type
  metadata, its children, and whether it comes from a built-in schema.
* ``CatalogEdge`` carries the parent's view of the child — the attribute name,
  type, required flag, and attribute-level metadata / validation.

Splitting these means From.derive can detach a leaf from its original
parent without dragging stale "as parent saw me" fields along, and
Grouped.derive can re-wire a node under a fresh CatalogEdge with appropriate
parent-side values.

Catalog conventions exploited here:

* Every catalog entity corresponds to an array-typed attribute
  (``object[]``).  Singleton object properties are flattened into dotted
  attribute names by SchemaInspector and never become entities, so
  composite nodes (those with children) are always reached via
  ``object[]`` edges.
* The root node is a virtual container whose children are the top-level
  entities; it is never emitted to the flat catalog.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from another_mood.components.shared import data_catalog as dc


@dataclass(frozen=True)
class CatalogEdge:
    """How a parent sees one of its children (the parent-side attribute view)."""

    name: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None


@dataclass(frozen=True)
class CatalogNode:
    metadata: Mapping[str, object] | None = None
    children: Sequence[tuple[CatalogEdge, "CatalogNode"]] = ()

    @property
    def is_entity(self) -> bool:
        """Whether this node materializes as a dc.Entity in the flat catalog.

        Equivalent to having children: scalar nodes surface only as
        attributes on their parent and never become entities.
        """
        return bool(self.children)

    def child_entry(self, name: str) -> tuple[CatalogEdge, "CatalogNode"]:
        """Return the (edge, child) entry reached by the edge named ``name``."""
        return next((e, c) for e, c in self.children if e.name == name)

    def child(self, name: str) -> "CatalogNode":
        """Return the child node reached by the edge named ``name``."""
        return self.child_entry(name)[1]

    @classmethod
    def build_from_catalog(cls, catalog: Sequence[dc.Entity]) -> "CatalogNode":
        """Build a virtual-root tree from a flat catalog list.

        The virtual root mirrors the records-side ``Sequence[Record]``
        wrapping that From.apply receives: every top-level entity hangs
        off it as an ``object[]`` edge so path traversal walks ``object[]``
        edges uniformly down to any leaf entity.
        """
        return cls(
            children=[
                (
                    CatalogEdge(name=entity.id, type="object[]", required=True),
                    _build_entity_node(entity, catalog),
                )
                for entity in _children_of(None, catalog)
            ],
        )

    def to_catalog_list(self, root_name: str) -> list[dc.Entity]:
        """Flatten this node into a list of dc.Entity records.

        The top entity gets ``root_name`` as its id; descendant ids are
        built by joining the chain of child edge names with dots, matching
        the access_path convention used by SchemaInspector.
        """
        return _flatten_entity(self, access_path=root_name, parent_entity_id=None)


def _build_entity_node(
    entity: dc.Entity,
    catalog: Sequence[dc.Entity],
) -> CatalogNode:
    """Build a CatalogNode body for ``entity`` (intrinsic fields only).

    ``entity.builtin`` is intentionally not carried into the tree: the
    catalog tree is a query-side intermediate, and a query view is never
    built-in by definition.  Composer marks query outputs as views after
    flattening; the built-in flag stays a flat-catalog concept.
    """
    sub_by_name = {e.id.rsplit(".", 1)[-1]: e for e in _children_of(entity.id, catalog)}
    return CatalogNode(
        metadata=entity.item_type.metadata,
        children=[
            (
                _edge_from_attribute(attr),
                _build_entity_node(sub_by_name[attr.id], catalog)
                if attr.entity
                else CatalogNode(),
            )
            for attr in entity.item_type.attributes
        ],
    )


def _edge_from_attribute(attr: dc.Attribute) -> CatalogEdge:
    """Build an CatalogEdge from a parent's dc.Attribute pointing at this child."""
    return CatalogEdge(
        name=attr.id,
        type=attr.type,
        required=attr.required,
        metadata=attr.metadata,
        validation=attr.validation,
    )


def _children_of(
    parent_id: str | None, catalog: Sequence[dc.Entity]
) -> Sequence[dc.Entity]:
    """Entities in ``catalog`` whose ``parent_entity`` equals ``parent_id``."""
    return [e for e in catalog if e.parent_entity == parent_id]


def _flatten_entity(
    node: CatalogNode,
    *,
    access_path: str,
    parent_entity_id: str | None,
) -> list[dc.Entity]:
    """Flatten ``node`` into a list of dc.Entity (parent first, descendants after).

    Caller's precondition: ``node.is_entity`` is True.  Scalar children
    of ``node`` are filtered out before recursion, so this function is
    only ever invoked on composite nodes.
    """
    self_entity = dc.Entity(
        id=access_path,
        item_type=_to_object_type(node, access_path=access_path),
        parent_entity=parent_entity_id,
    )
    descendants = [
        descendant
        for edge, child in node.children
        if child.is_entity
        for descendant in _flatten_entity(
            child,
            access_path=f"{access_path}.{edge.name}",
            parent_entity_id=access_path,
        )
    ]
    return [self_entity, *descendants]


def _to_object_type(node: CatalogNode, *, access_path: str) -> dc.ObjectType:
    """Build a dc.ObjectType for ``node`` reached at ``access_path``."""
    return dc.ObjectType(
        id=_item_type_id(access_path),
        attributes=[
            _to_attribute(child, edge=edge, access_path=f"{access_path}.{edge.name}")
            for edge, child in node.children
        ],
        metadata=node.metadata,
    )


def _to_attribute(
    node: CatalogNode, *, edge: CatalogEdge, access_path: str
) -> dc.Attribute:
    """Build a dc.Attribute for the (edge → node) connection at ``access_path``."""
    return dc.Attribute(
        id=edge.name,
        type=edge.type,
        required=edge.required,
        metadata=edge.metadata,
        validation=edge.validation,
        entity=access_path if node.is_entity else None,
        item_type=_item_type_id(access_path) if node.is_entity else None,
    )


def _item_type_id(access_path: str) -> str:
    """Compute the ObjectType id for an entity at ``access_path``.

    Mirrors SchemaInspector's recursive ``{...}.{name}.item`` convention
    by joining segments with ``.item.`` and appending a trailing ``.item``.
    """
    return ".item.".join(access_path.split(".")) + ".item"
