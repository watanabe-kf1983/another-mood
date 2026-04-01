"""Schema validation — validate YAML sources against JSON Schema.

Provides a general-purpose ``validate_source`` that parses a YAML string
with ruamel.yaml (preserving line/column positions) and validates it
against any jsonschema Validator.

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
from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from reqs_builder.components.normalizer.position_resolver import resolve_position
from reqs_builder.components.shared.diagnostic import Diagnostic

_SCHEMA_SCHEMA_PATH = (
    resources.files("reqs_builder.resources") / "schemas" / "schema-schema.yaml"
)

_VALIDATOR_SCHEMA: dict[str, Any] = yaml.safe_load(
    _SCHEMA_SCHEMA_PATH.read_text(encoding="utf-8")
)

_ruamel = YAML()


def validate_source(
    source: str, file: Path, validator: Validator
) -> Sequence[Diagnostic]:
    """Validate a YAML source string and return diagnostics with line numbers.

    Parses with ruamel.yaml to preserve positions, then validates against
    the given Validator.  Also catches ruamel.yaml parse errors (syntax
    errors, duplicate keys) and converts them to Diagnostic.
    """
    try:
        data: Any = _ruamel.load(source)  # type: ignore[no-untyped-call]
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        return [
            Diagnostic(
                file=file,
                line=mark.line + 1 if mark else None,
                column=mark.column + 1 if mark else None,
                message=getattr(exc, "problem", None) or str(exc),
                source="ruamel.yaml",
            )
        ]

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
    err: jsonschema.ValidationError, data: Any, file: Path
) -> Diagnostic:
    pos = resolve_position(err.absolute_path, data)
    return Diagnostic(
        file=file,
        line=pos.line,
        column=pos.column,
        message=err.message,
        source="jsonschema",
    )
