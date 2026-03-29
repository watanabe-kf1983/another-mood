"""Schema validation using the built-in SchemaSchema.

Loads the SchemaSchema from resources and validates user-defined schema
files against it.  Uses ruamel.yaml to preserve line/column positions
so that validation errors can point to exact YAML source locations.
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

_validator: Validator = jsonschema.Draft202012Validator(_VALIDATOR_SCHEMA)

_ruamel = YAML()


def validate_schema_file(
    data: Mapping[str, Any],
) -> Sequence[jsonschema.ValidationError]:
    """Validate a parsed schema file against SchemaSchema.

    Returns a list of validation errors (empty if valid).
    """
    # Mapping[str, Any] is not assignable to the recursive _JsonParameter alias
    # in the jsonschema stubs, but yaml.safe_load always produces JSON-compatible data.
    return list(_validator.iter_errors(data))  # type: ignore[arg-type]


def validate_schema_source(source: str, file: Path) -> Sequence[Diagnostic]:
    """Validate a YAML schema string and return diagnostics with line numbers.

    Parses with ruamel.yaml to preserve positions, then validates
    against SchemaSchema.  Also catches ruamel.yaml parse errors
    (syntax errors, duplicate keys) and converts them to Diagnostic.
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
        for err in _validator.iter_errors(data)
    ]


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
