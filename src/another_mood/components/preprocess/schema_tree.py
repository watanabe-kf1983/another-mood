"""SchemaTree — intermediate tree representation of JSON Schema.

Converts JSON Schema subset into a simple 3-node tree (ObjectNode,
ArrayNode, ValueNode), absorbing structural patterns like
additionalProperties and nested items.  The tree is then converted to
a ``dc.Node`` and flattened into a DataCatalog (entities + attributes)
for downstream consumption.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, assert_never, cast

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


# ── SchemaTree → DataCatalog (via dc.Node) ───────────────────────


def extract_entities(
    schema: Mapping[str, object],
    *,
    builtin: bool = False,
) -> Sequence[dc.Entity]:
    """Convert a root schema into a flat list of Entity.

    Each top-level property must be a collection (ArrayNode-wrapped
    ObjectNode in tree form); top-level non-collections are silently
    dropped.  ``builtin=True`` post-marks every emitted entity.
    """
    root = build_schema_tree(schema)
    if isinstance(root, ObjectNode):
        return [
            entity
            for prop in root.properties
            for entity in collect_entities(prop.name, prop.node, builtin=builtin)
        ]
    else:
        return []


def collect_entities(
    name: str,
    node: Node,
    *,
    builtin: bool = False,
) -> Sequence[dc.Entity]:
    """Return the entities one named SchemaTree contributes (empty if non-collection)."""
    catalog_node = _to_catalog_node(node)
    if not catalog_node.is_entity:
        return []
    flat = catalog_node.to_flat(name)
    return [replace(e, builtin=True) for e in flat] if builtin else flat


def _to_catalog_node(node: Node) -> dc.Node:
    obj = _unwrap_to_object(node)
    if obj is None:
        return dc.Node()
    # ArrayNode metadata wins: the outer dict-pattern schema owns the
    # type-level metadata; the inner ObjectNode describes structure only.
    metadata = node.metadata if isinstance(node, ArrayNode) else None
    return dc.Node(
        metadata=metadata or obj.metadata,
        children=list(_collect_edges(obj)),
    )


def _collect_edges(
    obj: ObjectNode,
) -> Iterable[tuple[dc.Edge, dc.Node]]:
    # Singleton ObjectNode properties surface as the singleton attribute
    # itself (type='object') plus their sub-properties flattened one level
    # deep into dotted-name scalars, matching SchemaInspector's "no
    # nested-object entities" convention.
    for prop in obj.properties:
        if isinstance(prop.node, ObjectNode):
            yield (_property_to_edge(prop), dc.Node())
            for sub in prop.node.properties:
                yield (
                    _property_to_edge(sub, name=f"{prop.name}.{sub.name}"),
                    dc.Node(),
                )
        else:
            yield (_property_to_edge(prop), _to_catalog_node(prop.node))


def _property_to_edge(prop: SchemaProperty, *, name: str | None = None) -> dc.Edge:
    return dc.Edge(
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
    match node:
        case ValueNode():
            return node.type
        case ObjectNode():
            return "object"
        case ArrayNode():
            return f"{_resolve_type(node.child)}[]"
        case _:
            assert_never(node)
