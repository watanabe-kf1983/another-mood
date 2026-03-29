"""Schema validation using the built-in SchemaSchema.

Loads the SchemaSchema from resources and validates user-defined schema
files against it.  Uses ruamel.yaml to preserve line/column positions
so that validation errors can point to exact YAML source locations.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
import jsonschema
from jsonschema.protocols import Validator
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from reqs_builder.components.normalizer.position_resolver import (
    Position,
    resolve_position,
)

_SCHEMA_SCHEMA_PATH = (
    resources.files("reqs_builder.resources") / "schemas" / "schema-schema.yaml"
)

_VALIDATOR_SCHEMA: dict[str, Any] = yaml.safe_load(
    _SCHEMA_SCHEMA_PATH.read_text(encoding="utf-8")
)

_validator: Validator = jsonschema.Draft202012Validator(_VALIDATOR_SCHEMA)

_ruamel = YAML()


@dataclass(frozen=True)
class ValidationIssue:
    """A schema validation error with source location."""

    message: str
    position: Position


def validate_schema_file(
    data: Mapping[str, Any],
) -> Sequence[jsonschema.ValidationError]:
    """Validate a parsed schema file against SchemaSchema.

    Returns a list of validation errors (empty if valid).
    """
    # Mapping[str, Any] is not assignable to the recursive _JsonParameter alias
    # in the jsonschema stubs, but yaml.safe_load always produces JSON-compatible data.
    return list(_validator.iter_errors(data))  # type: ignore[arg-type]


def validate_schema_source(source: str) -> Sequence[ValidationIssue]:
    """Validate a YAML schema string and return errors with line numbers.

    Parses with ruamel.yaml to preserve positions, then validates
    against SchemaSchema.
    """
    # TODO: catch ruamel.yaml.YAMLError (ParserError, ScannerError,
    # DuplicateKeyError) and convert to the pipeline error type once the
    # error model is redesigned (see normalizer.md TODO).
    data: Any = _ruamel.load(source)  # type: ignore[no-untyped-call]
    if not isinstance(data, Mapping):
        return [
            ValidationIssue(
                message="Schema file must be a YAML mapping",
                position=Position(line=1, column=1),
            )
        ]

    raw_errors: list[jsonschema.ValidationError] = list(
        _validator.iter_errors(data)  # type: ignore[arg-type]
    )
    return [
        ValidationIssue(
            message=err.message,
            position=resolve_position(err.absolute_path, data),
        )
        for err in raw_errors
    ]
