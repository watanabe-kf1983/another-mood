"""SchemaCatalog — build the data catalog tree from a JSON Schema.

Converts the accepted JSON Schema subset into the catalog's ``dc.Node`` /
``dc.Edge`` tree; ``dc.flatten_tree`` turns that into the flat entity
list the rest of the pipeline consumes.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import cast

from another_mood.components.shared.user_source.source_loader import UserStr
from another_mood.components.shared import data_catalog as dc

type SchemaNode = Mapping[str, object]

#: The record's own body paired with its metadata: what a collection
#: layer peels down to.
type RecordBody = tuple[Sequence[dc.Branch], Mapping[str, object] | None]

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

#: Identity of a map-pattern record: the map key, lifted into the record
#: as a field of its own.
_ID_BRANCH: dc.Branch = (dc.Edge(name="id", type="string", required=True), dc.Node())


# ── Schema → DataCatalog ─────────────────────────────────────────────


def collect_entities(schema: SchemaNode) -> Sequence[dc.Entity]:
    """Walk a root schema's top-level properties and collect their entities.

    Each top-level property must be a collection (a map, or an array of
    objects); top-level non-collections are silently dropped.
    """
    root = build_catalog_node(schema)
    return [
        entity
        for edge, child in root.children
        if dc.is_entity(edge, child)
        for entity in dc.flatten_tree(child, edge.name)
    ]


def build_catalog_node(schema: SchemaNode) -> dc.Node:
    """Build the catalog node for one schema position.

    Assumes the input schema has already passed meta-validation, which
    guarantees a ``type`` key on every node.
    """
    body = _record_body(schema)
    if body is None:
        return dc.Node()
    else:
        branches, record_metadata = body
        # The outermost collection layer wins over the record underneath:
        # on the map pattern the collection schema owns the type-level
        # metadata, and the record schema describes structure only.  An
        # intermediate array layer is not consulted at all.
        return dc.Node(
            metadata=_extract_metadata(schema) or record_metadata,
            children=branches,
        )


def _record_body(schema: SchemaNode) -> RecordBody | None:
    """Peel collection layers down to the record underneath, if there is one.

    Returns None where nothing composite sits at the position: a scalar,
    or an array whose elements are scalars.
    """
    if _is_record(schema):
        return _record_branches(schema), _extract_metadata(schema)
    elif _is_map(schema):
        return _map_body(schema)
    elif _is_array(schema):
        return _record_body(cast(SchemaNode, schema["items"]))
    else:
        return None


def _map_body(schema: SchemaNode) -> RecordBody:
    """Body of a map-pattern collection: one record per map entry."""
    additional = cast(SchemaNode, schema["additionalProperties"])
    if _is_record(additional):
        return (
            [_ID_BRANCH, *_record_branches(additional)],
            _extract_metadata(additional),
        )
    else:
        # A map of non-records becomes id/value pairs.  The synthesized
        # ``value`` branch carries no ``x-ref``: declaring one on a map's
        # value schema is not supported.
        value_edge, value_node = _to_branch("value", additional, required=True)
        return [_ID_BRANCH, (replace(value_edge, x_ref=None), value_node)], None


def _record_branches(schema: SchemaNode) -> Sequence[dc.Branch]:
    """Branches for the properties a record schema declares."""
    properties = cast(Mapping[str, SchemaNode], schema["properties"])
    required = frozenset(cast(Sequence[str] | None, schema.get("required")) or [])
    return [
        _to_branch(name, prop_schema, required=name in required)
        for name, prop_schema in properties.items()
    ]


def _to_branch(name: str, schema: SchemaNode, *, required: bool) -> dc.Branch:
    """The (Edge, Node) pair one declared property stands for."""
    return (
        dc.Edge(
            name=name,
            type=_type_name(schema),
            required=required,
            metadata=_extract_metadata(schema),
            # Only a scalar carries validation into the catalog: the
            # array- and object-level keywords have no slot of their own.
            validation=None if _is_composite(schema) else _extract_validation(schema),
            x_ref=_to_xref(schema.get("x-ref")),
        ),
        build_catalog_node(schema),
    )


def _type_name(schema: SchemaNode) -> str:
    """The catalog type string for a position, one ``[]`` per array layer."""
    if _is_array(schema):
        return f"{_type_name(cast(SchemaNode, schema['items']))}[]"
    elif _is_map(schema):
        # A map normalizes into an array of records.
        return "object[]"
    else:
        return cast(str, schema["type"])


def _to_xref(raw: object) -> dc.XRef | None:
    """Convert a property's raw ``x-ref:`` mapping into the catalog form."""
    if not isinstance(raw, Mapping):
        return None
    x_ref = cast(SchemaNode, raw)
    entity = cast(str, x_ref["entity"])
    if "attribute" in x_ref:
        return dc.XRef(entity=entity, attribute=cast(str, x_ref["attribute"]))
    elif isinstance(entity, UserStr):
        # Implicit "id" inherits entity's Location so coherence-check
        # diagnostics on the implicit FK target point at the entity: line.
        return dc.XRef(entity=entity, attribute=UserStr("id", entity.location))
    else:
        return dc.XRef(entity=entity, attribute="id")


# ── Schema shapes ────────────────────────────────────────────────────


def _is_record(schema: SchemaNode) -> bool:
    """A fixed-structure object: ``properties`` enumerates its fields."""
    return schema.get("type") == "object" and "properties" in schema


def _is_map(schema: SchemaNode) -> bool:
    """A homogeneous map: ``additionalProperties`` gives the value schema."""
    return schema.get("type") == "object" and isinstance(
        schema.get("additionalProperties"), Mapping
    )


def _is_array(schema: SchemaNode) -> bool:
    return schema.get("type") == "array" and "items" in schema


def _is_composite(schema: SchemaNode) -> bool:
    return _is_record(schema) or _is_map(schema) or _is_array(schema)


def _extract_metadata(schema: SchemaNode) -> Mapping[str, object] | None:
    """Extract metadata keywords from a schema node, in the schema's key order."""
    # Iterate the schema, not _METADATA_KEYS: a frozenset orders its members by
    # hash, randomized per process (PYTHONHASHSEED), so keying off it would make
    # the emitted order differ build-to-build.
    meta = {k: schema[k] for k in schema if k in _METADATA_KEYS}
    return meta or None


def _extract_validation(schema: SchemaNode) -> Mapping[str, object] | None:
    """Extract validation keywords from a schema node, in the schema's key order."""
    # Schema order, not _VALIDATION_KEYS order — see _extract_metadata.
    val = {k: schema[k] for k in schema if k in _VALIDATION_KEYS}
    return val or None
