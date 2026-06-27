"""Normalize core — shared file pipeline used by content/query modules.

Walks a source directory, parses Markdown / YAML inputs via
``source_loader``, validates them against a schema, interprets the
Markdown body of prose records (``prose``: title derivation + relative
link normalization, in one parse), applies dict-to-array normalization,
and yields the result for downstream emission.  Used by both
``content_normalizer`` and ``query_deriver``.

Also provides the schema-guided dict-to-array transformer that the
pipeline composes.
"""

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import cast

from another_mood.components.preprocess.prose import preprocess_prose
from another_mood.components.shared.user_source.source_loader import load_source
from another_mood.components.shared.user_source.validator import Validator
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)

# JSON-like str-keyed mappings.
type Schema = Mapping[str, object]
type DataMap = Mapping[str, object]


def iter_normalized(src_dir: Path, schema: Schema) -> Iterator[tuple[Path, object]]:
    """Yield (src_file, normalized_data) for each recognized source file.

    Runs ``check`` first so all validation errors surface together
    before any output is produced. Files whose extension is neither
    YAML nor Markdown are skipped.
    """
    check(src_dir, schema)
    for src_file in _iter_files(src_dir):
        data = load_source(src_file, src_dir)
        if data is not None:
            yield src_file, normalize_data(preprocess_prose(data), schema)


def check(src_dir: Path, schema: Schema) -> None:
    """Validate all files in src_dir against the given schema.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = Validator(schema)
    diagnostics: list[Diagnostic] = []
    for src_file in _iter_files(src_dir):
        try:
            data = load_source(src_file, src_dir)
        except FileValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        if data is not None:
            diagnostics.extend(
                issue.at_file(src_file) for issue in validator.validate(data)
            )
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def _iter_files(src_dir: Path) -> Sequence[Path]:
    """Recursively list regular files under src_dir (sorted)."""
    return [f for f in sorted(src_dir.rglob("*")) if f.is_file()]


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


def _flatten_dict(data: DataMap, additional_schema: Schema) -> list[dict[str, object]]:
    """Convert a dict-pattern object to an array with ``id`` fields.

    When additionalProperties is an object schema with properties, the
    value's properties are expanded directly.  For non-object types
    (string, number, etc.) the value is wrapped as ``{"id": key, "value": val}``.

    The synthesized ``id`` is always a string: YAML lets users write
    int/bool keys (``10:``), but the catalog declares the implicit
    ``id`` as string, and downstream consumers (x-ref target sets,
    URL/anchor generation) need a single canonical type.
    """
    if additional_schema.get("type") == "object" and "properties" in additional_schema:
        props = cast(Schema, additional_schema.get("properties"))
        return [
            {"id": str(key), **_recurse_properties(cast(DataMap, value), props)}
            for key, value in data.items()
        ]
    return [
        {"id": str(key), "value": normalize_data(value, additional_schema)}
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
