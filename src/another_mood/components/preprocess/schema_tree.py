"""SchemaTree — intermediate tree representation of JSON Schema.

Converts JSON Schema subset into a simple 3-node tree (ObjectNode,
ArrayNode, ValueNode), absorbing structural patterns like
additionalProperties and nested items.  The tree is then flattened
into a DataCatalog (entities + attributes) for downstream consumption.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from another_mood.components.preprocess.data_catalog import (
    CatalogAttribute,
    CatalogEntity,
)

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


# ── SchemaTree → DataCatalog ─────────────────────────────────────────


def extract_entities(
    schemas: Mapping[str, object],
    *,
    builtin: bool = False,
) -> list[CatalogEntity]:
    """Convert a schemas dict into a flat list of CatalogEntity."""
    entities: list[CatalogEntity] = []
    for name, schema in schemas.items():
        tree = build_schema_tree(cast(SchemaDict, schema))
        collect_entities(name, tree, entities, builtin=builtin)
    return entities


def collect_entities(
    name: str,
    node: Node,
    entities: list[CatalogEntity],
    *,
    builtin: bool = False,
) -> None:
    """Walk tree and collect entities from ObjectNodes.

    Any depth of ArrayNode wrapping is peeled off so that nested array
    schemas (e.g. `object[][]`) still yield an entity.
    """
    obj = _unwrap_to_object(node)
    if obj is None:
        return
    metadata = node.metadata if isinstance(node, ArrayNode) else None
    _emit_object_entity(name, obj, entities, metadata=metadata, builtin=builtin)


def _unwrap_to_object(node: Node) -> ObjectNode | None:
    """Peel any number of ArrayNode layers; return the inner ObjectNode if any."""
    while isinstance(node, ArrayNode):
        node = node.child
    return node if isinstance(node, ObjectNode) else None


def _to_catalog_attribute(
    attribute_id: str,
    prop: SchemaProperty,
    *,
    child_entity: str | None = None,
) -> CatalogAttribute:
    """Convert a SchemaProperty to a CatalogAttribute."""
    return CatalogAttribute(
        id=attribute_id,
        type=_resolve_type(prop.node),
        required=prop.required,
        metadata=prop.node.metadata,
        validation=(prop.node.validation if isinstance(prop.node, ValueNode) else None),
        child_entity=child_entity,
    )


def _emit_object_entity(
    name: str,
    obj: ObjectNode,
    entities: list[CatalogEntity],
    *,
    metadata: Mapping[str, object] | None = None,
    parent_entity: str | None = None,
    builtin: bool = False,
) -> None:
    """Emit a CatalogEntity from an ObjectNode, recursing into children."""
    catalog_attributes: list[CatalogAttribute] = []
    child_entities: list[tuple[str, ObjectNode]] = []

    for prop in obj.properties:
        child_entity_id: str | None = None
        if isinstance(prop.node, ArrayNode):
            child_obj = _unwrap_to_object(prop.node)
            if child_obj is not None:
                child_entity_id = f"{name}.{prop.name}"
                child_entities.append((child_entity_id, child_obj))

        catalog_attributes.append(
            _to_catalog_attribute(prop.name, prop, child_entity=child_entity_id)
        )

        if isinstance(prop.node, ObjectNode):
            for sub in prop.node.properties:
                catalog_attributes.append(
                    _to_catalog_attribute(f"{prop.name}.{sub.name}", sub)
                )

    # ArrayNode metadata takes precedence: the outer dict-pattern schema owns
    # the entity-level metadata (title, description, etc.), while the inner
    # ObjectNode describes the structure only.
    entities.append(
        CatalogEntity(
            id=name,
            attributes=catalog_attributes,
            metadata=metadata or obj.metadata,
            parent_entity=parent_entity,
            builtin=builtin,
        )
    )

    for child_name, child_obj in child_entities:
        _emit_object_entity(
            child_name, child_obj, entities, parent_entity=name, builtin=builtin
        )


def _resolve_type(node: Node) -> str:
    """Resolve a node to its type string for the data catalog."""
    if isinstance(node, ValueNode):
        return node.type
    if isinstance(node, ObjectNode):
        return "object"
    inner = _resolve_type(node.child)
    return f"{inner}[]"
