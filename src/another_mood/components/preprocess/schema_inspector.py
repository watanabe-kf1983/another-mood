"""SchemaInspector — validate and extract metadata from the user schema file.

Reads `schema_file`, validates it against the built-in SchemaSchema,
extracts a data catalog (entities + fields), and writes the result to
`out_dir`.  Built-in content schemas (e.g. prose) are emitted under
`out_dir/__builtin/` so their entities also surface in meta-docs.
"""

from collections.abc import Mapping
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
from another_mood.components.shared.json_data_model import load_model

_SCHEMA_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "schema-schema.yaml")
)

_BUILTIN_CONTENTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "content-schema.yaml")
)


@Component(out_dir="out_dir")
def inspect_schema(schema_file: Path, *, out_dir: Path) -> None:
    """Validate the user schema file and extract a data catalog."""
    check_schema(schema_file)
    _emit_catalog_file(schema_file, out_dir / schema_file.name)

    # Emit the built-in contents schema (prose) so its entities
    # appear in meta-documentation alongside user-defined schemas.
    _emit_catalog_file(
        _BUILTIN_CONTENTS_SCHEMA_FILE,
        out_dir / "__builtin" / _BUILTIN_CONTENTS_SCHEMA_FILE.name,
        builtin=True,
    )


def _emit_catalog_file(schema_file: Path, dst: Path, *, builtin: bool = False) -> None:
    """Extract data catalog from a single schema file and write it to dst."""
    data = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    catalog = extract_data_catalog(data, builtin=builtin)
    if not catalog:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml_dumper.dump({"__definition": catalog}, f)


def check_schema(schema_file: Path) -> None:
    """Validate the user schema file against SchemaSchema.

    Raises FileValidationError if the file has diagnostics.
    """
    if not schema_file.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    validator = build_schema_validator()
    diagnostics = list(validator.validate_yaml(schema_file))
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def extract_data_catalog(
    schema: Mapping[str, object], *, builtin: bool = False
) -> dict[str, Any]:
    """Extract data catalog (entities) from a root JSON Schema."""
    result: dict[str, Any] = {}

    properties = schema.get("properties")
    if isinstance(properties, Mapping) and properties:
        entities = extract_entities(
            cast(Mapping[str, object], properties), builtin=builtin
        )
        result["entities"] = [_strip_nones(asdict(e)) for e in entities]

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
    """Build a Validator for the user schema file (against built-in SchemaSchema)."""
    return Validator(load_model(_SCHEMA_SCHEMA_FILE))
