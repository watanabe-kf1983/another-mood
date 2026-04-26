"""CatalogNode — in-memory tree representation of the data catalog.

Unifies the persistence-layer dc.Entity / dc.ObjectType / dc.Attribute
trio into a single tree node, used as the input/output of every
``QueryNode.derive`` stage.  Each child is keyed by name in its parent's
``children`` sequence — names are not stored on the node itself, which
makes pipeline transforms ``replace``-and-rewire only.

Catalog conventions exploited here:

* Every catalog entity corresponds to an array-typed edge (object[]).
  Singleton object properties are flattened into dotted attribute names
  by SchemaInspector and never become entities, so composite Nodes
  (those with children) always carry ``type='object[]'``.
* The root Node is a virtual container whose children are the top-level
  entities; it is never emitted to the flat catalog.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from another_mood.components.shared import data_catalog as dc


@dataclass(frozen=True)
class CatalogNode:
    type: str
    required: bool
    attribute_metadata: Mapping[str, object] | None = None
    type_metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    children: Sequence[tuple[str, "CatalogNode"]] = ()
    builtin: bool = False

    @property
    def is_entity(self) -> bool:
        """Whether this node materializes as a dc.Entity in the flat catalog.

        Equivalent to having children: scalar nodes surface only as
        attributes on their parent and never become entities.
        """
        return bool(self.children)

    def child(self, name: str) -> "CatalogNode":
        """Return the child node keyed by ``name``."""
        return next(c for n, c in self.children if n == name)

    @classmethod
    def build_from_catalog(cls, catalog: Sequence[dc.Entity]) -> "CatalogNode":
        """Build a virtual-root tree from a flat catalog list.

        The virtual root mirrors the records-side ``Sequence[Record]``
        wrapping that From.apply receives: it has ``type='object[]'`` so
        that path traversal walks ``object[]`` edges uniformly down to
        any leaf entity.
        """
        return cls(
            type="object[]",
            required=True,
            children=[
                (entity.id, _build_entity_node(entity, None, catalog))
                for entity in _children_of(None, catalog)
            ],
        )

    def to_catalog_list(self, root_name: str) -> list[dc.Entity]:
        """Flatten this node into a list of dc.Entity records.

        The top entity gets ``root_name`` as its id; descendant ids are
        built by joining the chain of child names with dots, matching the
        access_path convention used by SchemaInspector.
        """
        return _flatten_entity(self, access_path=root_name, parent_entity_id=None)


def _build_entity_node(
    entity: dc.Entity,
    parent_attr: dc.Attribute | None,
    catalog: Sequence[dc.Entity],
) -> CatalogNode:
    """Build a CatalogNode for ``entity``.

    ``parent_attr`` supplies attribute-level fields (type, required,
    metadata, validation).  Pass None for top-level entities; defaults
    are ``type='object[]'``, ``required=True``, no metadata/validation.
    """
    sub_by_name = {e.id.rsplit(".", 1)[-1]: e for e in _children_of(entity.id, catalog)}
    children: list[tuple[str, CatalogNode]] = []
    for attr in entity.item_type.attributes:
        if attr.entity:
            sub_entity = sub_by_name[attr.id]
            children.append((attr.id, _build_entity_node(sub_entity, attr, catalog)))
        else:
            children.append((attr.id, _build_scalar_node(attr)))
    return CatalogNode(
        type=parent_attr.type if parent_attr else "object[]",
        required=parent_attr.required if parent_attr else True,
        attribute_metadata=parent_attr.metadata if parent_attr else None,
        type_metadata=entity.item_type.metadata,
        validation=parent_attr.validation if parent_attr else None,
        children=children,
        builtin=entity.builtin,
    )


def _children_of(
    parent_id: str | None, catalog: Sequence[dc.Entity]
) -> Sequence[dc.Entity]:
    """Entities in ``catalog`` whose ``parent_entity`` equals ``parent_id``."""
    return [e for e in catalog if e.parent_entity == parent_id]


def _build_scalar_node(attr: dc.Attribute) -> CatalogNode:
    """Build a CatalogNode for a non-composite attribute (no entity ref)."""
    return CatalogNode(
        type=attr.type,
        required=attr.required,
        attribute_metadata=attr.metadata,
        validation=attr.validation,
    )


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
        builtin=node.builtin,
    )
    descendants = [
        descendant
        for name, child in node.children
        if child.is_entity
        for descendant in _flatten_entity(
            child,
            access_path=f"{access_path}.{name}",
            parent_entity_id=access_path,
        )
    ]
    return [self_entity, *descendants]


def _to_object_type(node: CatalogNode, *, access_path: str) -> dc.ObjectType:
    """Build a dc.ObjectType for ``node`` reached at ``access_path``."""
    return dc.ObjectType(
        id=_item_type_id(access_path),
        attributes=[
            _to_attribute(child, name=name, access_path=f"{access_path}.{name}")
            for name, child in node.children
        ],
        metadata=node.type_metadata,
    )


def _to_attribute(node: CatalogNode, *, name: str, access_path: str) -> dc.Attribute:
    """Build a dc.Attribute for ``node`` reached at ``access_path`` under ``name``."""
    return dc.Attribute(
        id=name,
        type=node.type,
        required=node.required,
        metadata=node.attribute_metadata,
        validation=node.validation,
        entity=access_path if node.is_entity else None,
        item_type=_item_type_id(access_path) if node.is_entity else None,
    )


def _item_type_id(access_path: str) -> str:
    """Compute the ObjectType id for an entity at ``access_path``.

    Mirrors SchemaInspector's recursive ``{...}.{name}.item`` convention
    by joining segments with ``.item.`` and appending a trailing ``.item``.
    """
    return ".item.".join(access_path.split(".")) + ".item"
