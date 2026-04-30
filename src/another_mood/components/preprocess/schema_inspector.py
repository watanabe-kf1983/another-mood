"""SchemaInspector — validate and extract metadata from the user schema file.

Reads `schema_file`, validates it against the built-in SchemaSchema,
extracts a data catalog (entities + fields), and writes the result to
`out_dir`.  Built-in content schemas (e.g. prose) are emitted under
`out_dir/__builtin/` so their entities also surface in meta-docs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import resources
from pathlib import Path

import yaml

from another_mood.components.preprocess.schema_tree import (
    ObjectNode,
    build_schema_tree,
    collect_entities,
)
from another_mood.components.preprocess.source_loader import parse_yaml
from another_mood.components.preprocess.validator import Validator
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.diagnostic import FileValidationError
from another_mood.components.shared.json_data_model import load_model, save_model


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
    schema = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    entities = extract_entities(schema, builtin=builtin)
    if entities:
        catalog = {"entities": [e.to_dict() for e in entities]}
        save_model(dst, {"__definition": catalog})


def check_schema(schema_file: Path) -> None:
    """Validate the user schema file against SchemaSchema.

    Raises FileValidationError if the file has diagnostics.
    """
    if not schema_file.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    validator = build_schema_validator()
    data = parse_yaml(schema_file)
    diagnostics = list(validator.validate(data, schema_file))
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def extract_entities(
    schema: Mapping[str, object], *, builtin: bool = False
) -> Sequence[dc.Entity]:
    """Convert a root schema into a flat list of Entity."""
    root = build_schema_tree(schema)
    if not isinstance(root, ObjectNode):
        raise ValueError(
            f"Root schema must be an object with properties; got {type(root).__name__}"
        )
    entities = collect_entities(root)
    return [replace(e, builtin=True) for e in entities] if builtin else entities


def build_schema_validator() -> Validator:
    """Build a Validator for the user schema file (against built-in SchemaSchema)."""
    return Validator(load_model(_SCHEMA_SCHEMA_FILE))
