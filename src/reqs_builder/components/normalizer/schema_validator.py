"""Schema validation using the built-in SchemaSchema.

Loads the SchemaSchema from resources and validates user-defined schema
files against it.
"""

from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

import yaml
from jsonschema import Draft202012Validator, ValidationError
from jsonschema.protocols import Validator

_SCHEMA_SCHEMA_PATH = (
    resources.files("reqs_builder.resources") / "schemas" / "schema-schema.yaml"
)

_VALIDATOR_SCHEMA: dict[str, Any] = yaml.safe_load(
    _SCHEMA_SCHEMA_PATH.read_text(encoding="utf-8")
)


def validate_schema_file(
    data: Mapping[str, Any],
) -> Sequence[ValidationError]:
    """Validate a parsed schema file against SchemaSchema.

    Returns a list of validation errors (empty if valid).
    """
    validator: Validator = Draft202012Validator(_VALIDATOR_SCHEMA)
    # Mapping[str, Any] is not assignable to the recursive _JsonParameter alias
    # in the jsonschema stubs, but yaml.safe_load always produces JSON-compatible data.
    return list(validator.iter_errors(data))  # type: ignore[arg-type]
