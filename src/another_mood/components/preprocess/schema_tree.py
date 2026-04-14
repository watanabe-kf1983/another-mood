"""SchemaTree — intermediate tree representation of JSON Schema.

Converts JSON Schema subset into a simple 3-node tree (ObjectNode,
ArrayNode, ValueNode), absorbing structural patterns like
additionalProperties and nested items.  The tree is then flattened
into a DataCatalog (entities + fields) for downstream consumption.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from another_mood.components.preprocess.data_catalog import (
    CatalogEntity,
    CatalogField,
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
class SchemaField:
    """Edge between parent ObjectNode and child Node."""

    name: str
    required: bool
    node: Node


@dataclass(frozen=True)
class ObjectNode:
    """Object node — holds named fields (properties)."""

    fields: Sequence[SchemaField]
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

    fields = [
        SchemaField(
            name=prop_name,
            required=prop_name in required_set,
            node=build_schema_tree(prop_schema),
        )
        for prop_name, prop_schema in properties.items()
    ]
    return ObjectNode(fields=fields, metadata=metadata)


def _build_array_from_additional(
    schema: Mapping[str, object],
    metadata: Mapping[str, object] | None,
) -> ArrayNode:
    """Build ArrayNode from a schema with 'additionalProperties' (dict pattern)."""
    additional = cast(SchemaDict, schema["additionalProperties"])
    additional_type: str | None = additional.get("type")

    if additional_type == "object" and "properties" in additional:
        inner = _build_object_from_properties(additional, _extract_metadata(additional))
        id_field = SchemaField(name="id", required=True, node=ValueNode(type="string"))
        child = ObjectNode(
            fields=[id_field, *inner.fields],
            metadata=inner.metadata,
        )
    else:
        value_node = build_schema_tree(additional)
        child = ObjectNode(
            fields=[
                SchemaField(name="id", required=True, node=ValueNode(type="string")),
                SchemaField(name="value", required=True, node=value_node),
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
    """Walk tree and collect entities from ObjectNodes."""
    if isinstance(node, ArrayNode) and isinstance(node.child, ObjectNode):
        _emit_object_entity(
            name, node.child, entities, metadata=node.metadata, builtin=builtin
        )
    elif isinstance(node, ObjectNode):
        _emit_object_entity(name, node, entities, builtin=builtin)


def _to_catalog_field(
    field_id: str,
    field: SchemaField,
    *,
    child_entity: str | None = None,
) -> CatalogField:
    """Convert a SchemaField to a CatalogField."""
    return CatalogField(
        id=field_id,
        type=_resolve_type(field.node),
        required=field.required,
        metadata=field.node.metadata,
        validation=(
            field.node.validation if isinstance(field.node, ValueNode) else None
        ),
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
    catalog_fields: list[CatalogField] = []
    child_entities: list[tuple[str, ObjectNode]] = []

    for field in obj.fields:
        child_entity_id: str | None = None
        if isinstance(field.node, ArrayNode) and isinstance(
            field.node.child, ObjectNode
        ):
            child_entity_id = f"{name}.{field.name}"
            child_entities.append((child_entity_id, field.node.child))

        catalog_fields.append(
            _to_catalog_field(field.name, field, child_entity=child_entity_id)
        )

        if isinstance(field.node, ObjectNode):
            for sub in field.node.fields:
                catalog_fields.append(
                    _to_catalog_field(f"{field.name}.{sub.name}", sub)
                )

    # ArrayNode metadata takes precedence: the outer dict-pattern schema owns
    # the entity-level metadata (title, description, etc.), while the inner
    # ObjectNode describes the structure only.
    entities.append(
        CatalogEntity(
            id=name,
            fields=catalog_fields,
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
