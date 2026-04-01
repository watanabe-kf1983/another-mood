"""Schema validation — validate data against JSON Schema.

Provides ``validate_data`` that validates parsed data against any
jsonschema Validator, returning Diagnostic objects.  When the data
carries ruamel.yaml position metadata, diagnostics include line/column.

Builder functions create Validators for specific use-cases:

* ``build_schema_validator`` — validates user schema files against the
  built-in SchemaSchema.
* ``build_content_validator`` — validates content files against
  user-defined schemas.
"""

from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from jsonschema.protocols import Validator

from reqs_builder.components.preprocess.position_resolver import resolve_position
from reqs_builder.components.shared.diagnostic import Diagnostic

_SCHEMA_SCHEMA_PATH = (
    resources.files("reqs_builder.resources") / "schemas" / "schema-schema.yaml"
)

_VALIDATOR_SCHEMA: dict[str, Any] = yaml.safe_load(
    _SCHEMA_SCHEMA_PATH.read_text(encoding="utf-8")
)


def validate_data(data: Any, file: Path, validator: Validator) -> Sequence[Diagnostic]:
    """Validate parsed data and return diagnostics.

    When *data* is a ruamel.yaml object (CommentedMap/CommentedSeq),
    diagnostics include line/column positions.  For plain dicts/lists,
    line and column are None.
    """
    return [
        _jsonschema_error_to_diagnostic(err, data, file)
        for err in validator.iter_errors(data)
    ]


def build_schema_validator() -> Validator:
    """Build a Validator for user schema files (against built-in SchemaSchema)."""
    return jsonschema.Draft202012Validator(_VALIDATOR_SCHEMA)


def build_content_validator(schemas: Mapping[str, Any]) -> Validator:
    """Build a Validator for content files from user-defined schemas.

    Each key in *schemas* maps a schema name to its JSON Schema definition.
    The returned Validator checks that content file top-level keys conform
    to their corresponding schema.
    """
    return jsonschema.Draft202012Validator({"type": "object", "properties": schemas})


def _jsonschema_error_to_diagnostic(
    err: jsonschema.ValidationError, data: object, file: Path
) -> Diagnostic:
    pos = resolve_position(err.absolute_path, data)
    return Diagnostic(
        file=file,
        line=pos.line if pos else None,
        column=pos.column if pos else None,
        message=err.message,
        source="jsonschema",
    )
