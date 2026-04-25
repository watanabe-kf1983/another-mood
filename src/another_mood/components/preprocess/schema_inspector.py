"""SchemaInspector — validate and extract metadata from user schema files.

Reads all YAML files from schemas_dir, validates each against the
built-in SchemaSchema, extracts a data catalog (entities + fields),
and writes the result to data_catalog_dir.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from importlib import resources
from pathlib import Path
from typing import Any, cast

import yaml

from another_mood.components.preprocess.schema_tree import extract_entities
from another_mood.components.preprocess.validator import Validator
from another_mood.components.shared import yaml_dumper
from another_mood.components.shared.component import Component
from another_mood.components.shared.diagnostic import FileValidationError
from another_mood.components.shared.file_type import FileType
from another_mood.components.shared.json_data_model import load_model

_SCHEMA_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "schema-schema.yaml")
)

_BUILTIN_CONTENTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "content-schema.yaml")
)


@Component(out_dir="out_dir")
def inspect_schema(schemas_dir: Path, *, out_dir: Path) -> None:
    """Validate schema files and extract data catalog per file."""
    schema_files = _list_yaml_files(schemas_dir)
    check_schema(schema_files)

    for schema_file in schema_files:
        rel = schema_file.relative_to(schemas_dir)
        _emit_catalog_file(schema_file, out_dir / rel)

    # Emit the built-in contents schema (prose) so its entities
    # appear in meta-documentation alongside user-defined schemas.
    _emit_catalog_file(
        _BUILTIN_CONTENTS_SCHEMA_FILE,
        out_dir / "__builtin" / _BUILTIN_CONTENTS_SCHEMA_FILE.name,
        builtin=True,
    )


def _list_yaml_files(src_dir: Path) -> Sequence[Path]:
    return [f for f in sorted(src_dir.rglob("*")) if FileType.YAML.match(f)]


def _emit_catalog_file(schema_file: Path, dst: Path, *, builtin: bool = False) -> None:
    """Extract data catalog from a single schema file and write it to dst."""
    data = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    catalog = extract_data_catalog(data, builtin=builtin)
    if not catalog:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
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
    schema: Mapping[str, object], *, builtin: bool = False
) -> dict[str, Any]:
    """Extract data catalog (entities + references) from merged schema data."""
    result: dict[str, Any] = {}

    schemas = schema.get("schemas")
    if isinstance(schemas, Mapping) and schemas:
        entities = extract_entities(
            cast(Mapping[str, object], schemas), builtin=builtin
        )
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
    return Validator(load_model(_SCHEMA_SCHEMA_FILE))
