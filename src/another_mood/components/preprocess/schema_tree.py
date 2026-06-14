"""SchemaTree — intermediate tree representation of JSON Schema.

Converts JSON Schema subset into a simple 3-node tree (ObjectNode,
ArrayNode, ValueNode), absorbing structural patterns like
additionalProperties and nested items.  The tree is then converted to
a ``dc.Node`` and flattened into a DataCatalog (entities + attributes)
for downstream consumption.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, assert_never, cast

from another_mood.components.shared.user_source.source_loader import UserStr
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
    x_ref: Mapping[str, object] | None = None


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
    """Build a SchemaTree node from a JSON Schema subset definition.

    Assumes the input schema has already passed meta-validation, which
    guarantees a ``type`` key on every node.
    """
    schema_type = cast(str, schema["type"])
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
        type=schema_type,
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
            x_ref=_extract_x_ref(prop_schema),
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
    """Extract metadata keywords from a schema node, in the schema's key order."""
    # Iterate the schema, not _METADATA_KEYS: a frozenset orders its members by
    # hash, randomized per process (PYTHONHASHSEED), so keying off it would make
    # the emitted order differ build-to-build.
    meta = {k: schema[k] for k in schema if k in _METADATA_KEYS}
    return meta or None


def _extract_validation(
    schema: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Extract validation keywords from a schema node, in the schema's key order."""
    # Schema order, not _VALIDATION_KEYS order — see _extract_metadata.
    val = {k: schema[k] for k in schema if k in _VALIDATION_KEYS}
    return val or None


def _extract_x_ref(schema: Mapping[str, object]) -> Mapping[str, object] | None:
    """Extract the raw ``x-ref:`` mapping from a property schema, if any.

    Returns the raw mapping (or None); conversion to the catalog-layer
    ``dc.XRef`` dataclass is deferred to :func:`_property_to_edge`,
    where the schema-tree representation crosses over to the data
    catalog. Mirrors how ``metadata`` / ``validation`` are stored as
    plain mappings on the tree nodes.
    """
    raw = schema.get("x-ref")
    if not isinstance(raw, Mapping):
        return None
    return cast(Mapping[str, object], raw)


# ── SchemaTree → DataCatalog (via dc.Node) ───────────────────────


def collect_entities(root: ObjectNode) -> Sequence[dc.Entity]:
    """Walk a root tree's top-level properties and collect their entities.

    Each top-level property must be a collection (ArrayNode-wrapped
    ObjectNode in tree form); top-level non-collections are silently
    dropped.
    """
    catalog_node = to_catalog_node(root)
    return [
        entity
        for edge, child in catalog_node.children
        if child.is_entity
        for entity in dc.flatten_tree(child, edge.name)
    ]


def to_catalog_node(node: Node) -> dc.Node:
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
    # A singleton property (ObjectNode child of obj) is inlined into the
    # parent entity rather than becoming its own entity.  Each singleton
    # contributes two kinds of edges:
    #   - the singleton itself, as a scalar `object` edge with no child;
    #   - one `<singleton>.<sub>` dotted-name edge per sub-property.
    # If a sub-property is a collection (ArrayNode), its child Node is
    # carried along so a nested entity hangs off the dotted edge.  Scalar
    # and nested-singleton sub-properties degrade to opaque edges with
    # no child.
    for prop in obj.properties:
        if isinstance(prop.node, ObjectNode):
            yield (_property_to_edge(prop), dc.Node())
            for sub in prop.node.properties:
                sub_child = (
                    to_catalog_node(sub.node)
                    if isinstance(sub.node, ArrayNode)
                    else dc.Node()
                )
                yield (
                    _property_to_edge(sub, name=f"{prop.name}.{sub.name}"),
                    sub_child,
                )
        else:
            yield (_property_to_edge(prop), to_catalog_node(prop.node))


def _property_to_edge(prop: SchemaProperty, *, name: str | None = None) -> dc.Edge:
    return dc.Edge(
        name=name if name is not None else prop.name,
        type=_resolve_type(prop.node),
        required=prop.required,
        metadata=prop.node.metadata,
        validation=prop.node.validation if isinstance(prop.node, ValueNode) else None,
        x_ref=_to_xref(prop.x_ref),
    )


def _to_xref(raw: Mapping[str, object] | None) -> dc.XRef | None:
    if raw is None:
        return None
    entity = cast(str, raw["entity"])
    if "attribute" in raw:
        attribute = cast(str, raw["attribute"])
    elif isinstance(entity, UserStr):
        # Implicit "id" inherits entity's Location so coherence-check
        # diagnostics on the implicit FK target point at the entity: line.
        attribute = UserStr("id", entity.location)
    else:
        attribute = "id"
    return dc.XRef(entity=entity, attribute=attribute)


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
