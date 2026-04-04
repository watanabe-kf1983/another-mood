"""Dict-to-array normalization for additionalProperties pattern.

Converts dict-keyed objects into arrays with an ``id`` field,
guided by the JSON Schema structure. Recurses into nested
additionalProperties and array items.
"""

from collections.abc import Mapping, Sequence
from typing import cast

# JSON-like str-keyed mappings.
type Schema = Mapping[str, object]
type DataMap = Mapping[str, object]


def normalize_data(data: object, schema: Schema) -> object:
    """Normalize data according to schema's additionalProperties patterns."""
    schema_type = schema.get("type")

    if schema_type == "object":
        data_map = cast(DataMap, data)
        if schema_properties := schema.get("properties"):
            return _recurse_properties(data_map, cast(Schema, schema_properties))
        if schema_additional := schema.get("additionalProperties"):
            return _flatten_dict(data_map, cast(Schema, schema_additional))

    if schema_type == "array":
        items = cast(Sequence[object], data)
        if schema_items := schema.get("items"):
            return _recurse_items(items, cast(Schema, schema_items))

    return data


# ── transformations ───────────────────────────────────────────────


def _flatten_dict(data: DataMap, additional_schema: Schema) -> list[dict[str, object]]:
    """Convert a dict-pattern object to an array with ``id`` fields."""
    props = cast(Schema, additional_schema.get("properties"))
    return [
        {"id": key, **_recurse_properties(cast(DataMap, value), props)}
        for key, value in data.items()
    ]


def _recurse_properties(data: DataMap, properties: Schema) -> dict[str, object]:
    """Recurse into each property value using its sub-schema."""
    return {
        key: normalize_data(value, cast(Schema, properties[key]))
        if key in properties
        else value
        for key, value in data.items()
    }


def _recurse_items(data: Sequence[object], items_schema: Schema) -> list[object]:
    """Recurse into each element of an array."""
    return [normalize_data(item, items_schema) for item in data]
