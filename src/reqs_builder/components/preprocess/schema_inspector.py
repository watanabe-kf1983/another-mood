"""SchemaInspector — validate and extract metadata from user schema files.

Reads all YAML files from schema_dir, validates each against the
built-in SchemaSchema, extracts a data catalog (entities + fields),
and writes the result to data_catalog_dir.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from importlib import resources
from pathlib import Path
from typing import Any, cast

from reqs_builder.components.preprocess.schema_tree import extract_entities
from reqs_builder.components.preprocess.validator import Validator
from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import FileValidationError
from reqs_builder.components.shared.json_data_model import load_yamls

_SCHEMA_SCHEMA_DIR = Path(
    str(resources.files("reqs_builder.resources") / "schemas" / "schema")
)


@Component(out_dir="out_dir")
def inspect_schema(schema_dir: Path, *, out_dir: Path) -> None:
    """Validate schema files and extract data catalog."""
    schema_files = [f for f in sorted(schema_dir.rglob("*.yaml")) if f.is_file()]
    check_schema(schema_files)

    merged = load_yamls(schema_dir)
    catalog = extract_data_catalog(merged)
    if catalog:
        with (out_dir / "__definition.yaml").open("w") as f:
            yaml_dumper.dump({"__definition": catalog}, f)


def check_schema(schema_files: Sequence[Path]) -> None:
    """Validate schema files against SchemaSchema.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = build_schema_validator()
    diagnostics = [d for f in schema_files for d in validator.validate_yaml(f)]
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def extract_data_catalog(
    schema: Mapping[str, object],
) -> dict[str, Any]:
    """Extract data catalog (entities + references) from merged schema data."""
    result: dict[str, Any] = {}

    schemas = schema.get("schemas")
    if isinstance(schemas, Mapping) and schemas:
        entities = extract_entities(cast(Mapping[str, object], schemas))
        result["entities"] = [_strip_nones(asdict(e)) for e in entities]

    references = schema.get("references")
    if references:
        result["references"] = references

    return result


def _strip_nones(d: Any) -> Any:  # noqa: ANN401
    """Recursively remove keys with None values from dicts."""
    if isinstance(d, dict):
        return {
            k: _strip_nones(v)
            for k, v in cast(dict[str, Any], d).items()
            if v is not None
        }
    if isinstance(d, list):
        return [_strip_nones(item) for item in cast(list[Any], d)]
    return d


def build_schema_validator() -> Validator:
    """Build a Validator for user schema files (against built-in SchemaSchema)."""
    return Validator(load_yamls(_SCHEMA_SCHEMA_DIR))
