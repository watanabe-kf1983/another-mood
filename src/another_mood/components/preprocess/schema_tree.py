"""SchemaTree — intermediate tree representation of JSON Schema.

Converts JSON Schema subset into a simple 3-node tree (ObjectNode,
ArrayNode, ValueNode), absorbing structural patterns like
additionalProperties and nested items.  The tree is then converted to
a CatalogNode and flattened into a DataCatalog (entities + attributes)
for downstream consumption.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from another_mood.components.composer.catalog_node import CatalogEdge, CatalogNode
from another_mood.components.shared import data_catalog as dc

# ── Node definitions ─────────────────────────────────────────────────

type Node = ObjectNode | ArrayNode | ValueNode
type SchemaDict = dict[str, Any]


@dataclass(frozen=True)
class ValueNode:
    """Leaf node — scalar type (string, number, integer, boolean, etc.)."""

    type: str
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ArrayNode:
    """Array node — holds exactly one child (the items type)."""

    child: Node
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class SchemaProperty:
    """Edge between parent ObjectNode and child Node."""

    name: str
    required: bool
    node: Node


@dataclass(frozen=True)
class ObjectNode:
    """Object node — holds named properties."""

    properties: Sequence[SchemaProperty]
    metadata: Mapping[str, object] | None = None


# ── Schema → SchemaTree ──────────────────────────────────────────────

_METADATA_KEYS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
        "format",
    }
)

_VALIDATION_KEYS = frozenset(
    {
        "enum",
        "const",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)


def build_schema_tree(schema: Mapping[str, object]) -> Node:
    """Build a SchemaTree node from a JSON Schema subset definition."""
    schema_type = schema.get("type")
    metadata = _extract_metadata(schema)

    if schema_type == "object":
        if "properties" in schema:
            return _build_object_from_properties(schema, metadata)
        if "additionalProperties" in schema:
            return _build_array_from_additional(schema, metadata)

    if schema_type == "array":
        items = cast(SchemaDict, schema["items"])
        return ArrayNode(child=build_schema_tree(items), metadata=metadata)

    return ValueNode(
        type=str(schema_type) if schema_type else "string",
        metadata=metadata,
        validation=_extract_validation(schema),
    )


def _build_object_from_properties(
    schema: Mapping[str, object],
    metadata: Mapping[str, object] | None,
) -> ObjectNode:
    """Build ObjectNode from a schema with 'properties'."""
    properties = cast(Mapping[str, SchemaDict], schema["properties"])
    required_list = cast(list[str] | None, schema.get("required"))
    required_set = frozenset(required_list or [])

    schema_properties = [
        SchemaProperty(
            name=prop_name,
            required=prop_name in required_set,
            node=build_schema_tree(prop_schema),
        )
        for prop_name, prop_schema in properties.items()
    ]
    return ObjectNode(properties=schema_properties, metadata=metadata)


def _build_array_from_additional(
    schema: Mapping[str, object],
    metadata: Mapping[str, object] | None,
) -> ArrayNode:
    """Build ArrayNode from a schema with 'additionalProperties' (dict pattern)."""
    additional = cast(SchemaDict, schema["additionalProperties"])
    additional_type: str | None = additional.get("type")

    if additional_type == "object" and "properties" in additional:
        inner = _build_object_from_properties(additional, _extract_metadata(additional))
        id_property = SchemaProperty(
            name="id", required=True, node=ValueNode(type="string")
        )
        child = ObjectNode(
            properties=[id_property, *inner.properties],
            metadata=inner.metadata,
        )
    else:
        value_node = build_schema_tree(additional)
        child = ObjectNode(
            properties=[
                SchemaProperty(name="id", required=True, node=ValueNode(type="string")),
                SchemaProperty(name="value", required=True, node=value_node),
            ]
        )

    return ArrayNode(child=child, metadata=metadata)


def _extract_metadata(
    schema: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Extract metadata keywords from a schema node."""
    meta = {k: schema[k] for k in _METADATA_KEYS if k in schema}
    return meta or None


def _extract_validation(
    schema: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Extract validation keywords from a schema node."""
    val = {k: schema[k] for k in _VALIDATION_KEYS if k in schema}
    return val or None


# ── SchemaTree → DataCatalog (via CatalogNode) ───────────────────────


def extract_entities(
    schemas: Mapping[str, object],
    *,
    builtin: bool = False,
) -> list[dc.Entity]:
    """Convert a schemas dict into a flat list of Entity.

    Each top-level entry must be a collection (ArrayNode-wrapped
    ObjectNode in tree form); top-level non-collections are silently
    dropped.  ``builtin=True`` post-marks every emitted entity.
    """
    return [
        entity
        for name, schema in schemas.items()
        for entity in collect_entities(
            name, build_schema_tree(cast(SchemaDict, schema)), builtin=builtin
        )
    ]


def collect_entities(
    name: str,
    node: Node,
    *,
    builtin: bool = False,
) -> list[dc.Entity]:
    """Return the entities one named SchemaTree contributes.

    Builds a CatalogNode for the tree and uses ``to_catalog_list`` to
    flatten — id naming, parent_entity links, and dotted-attribute
    handling for nested singletons all live in the CatalogNode layer.
    Non-collection top levels yield an empty list.
    """
    catalog_node = _to_catalog_node(node)
    if not catalog_node.is_entity:
        return []
    flat = catalog_node.to_catalog_list(name)
    return [replace(e, builtin=True) for e in flat] if builtin else flat


def _to_catalog_node(node: Node) -> CatalogNode:
    """Convert a SchemaTree node (entity-shaped) into a CatalogNode body.

    Returns an empty CatalogNode for nodes that don't materialize as
    entities (scalars, arrays of scalars), so the caller can filter
    them via ``CatalogNode.is_entity``.

    For ArrayNode-wrapped objects, the outer ArrayNode's metadata wins
    over the inner ObjectNode's — the dict-pattern schema owns the
    type-level metadata, the inner shape describes structure only.
    """
    obj = _unwrap_to_object(node)
    if obj is None:
        return CatalogNode()
    metadata = node.metadata if isinstance(node, ArrayNode) else None
    return CatalogNode(
        metadata=metadata or obj.metadata,
        children=list(_collect_edges(obj)),
    )


def _collect_edges(
    obj: ObjectNode,
) -> Iterable[tuple[CatalogEdge, CatalogNode]]:
    """Yield ``(edge, child)`` entries for an ObjectNode's properties.

    Singleton ObjectNode properties surface as the singleton attribute
    itself (``type='object'``) plus its sub-properties flattened one
    level deep into dotted-name scalar children, mirroring
    SchemaInspector's "no nested-object entities" convention.
    """
    for prop in obj.properties:
        if isinstance(prop.node, ObjectNode):
            yield (_property_to_edge(prop), CatalogNode())
            for sub in prop.node.properties:
                yield (
                    _property_to_edge(sub, name=f"{prop.name}.{sub.name}"),
                    CatalogNode(),
                )
        else:
            yield (_property_to_edge(prop), _to_catalog_node(prop.node))


def _property_to_edge(prop: SchemaProperty, *, name: str | None = None) -> CatalogEdge:
    """Build a CatalogEdge from a SchemaProperty (optionally renaming it)."""
    return CatalogEdge(
        name=name if name is not None else prop.name,
        type=_resolve_type(prop.node),
        required=prop.required,
        metadata=prop.node.metadata,
        validation=prop.node.validation if isinstance(prop.node, ValueNode) else None,
    )


def _unwrap_to_object(node: Node) -> ObjectNode | None:
    """Peel any number of ArrayNode layers; return the inner ObjectNode if any."""
    while isinstance(node, ArrayNode):
        node = node.child
    return node if isinstance(node, ObjectNode) else None


def _resolve_type(node: Node) -> str:
    """Resolve a node to its type string for the data catalog."""
    if isinstance(node, ValueNode):
        return node.type
    if isinstance(node, ObjectNode):
        return "object"
    inner = _resolve_type(node.child)
    return f"{inner}[]"
