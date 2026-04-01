"""Validation infrastructure — parse YAML and validate against JSON Schema.

Provides shared building blocks used by both SchemaInspector and Normalizer:

* ``parse_yaml`` — parse YAML with ruamel.yaml, preserving source positions
  for line-accurate diagnostics.
* ``validate_data`` — validate parsed data against any jsonschema Validator,
  returning Diagnostic objects.
* ``build_content_validator`` — build a Validator for content files against
  user-defined schemas.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.protocols import Validator
from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from reqs_builder.components.preprocess.position_resolver import resolve_position
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_ruamel = YAML()


def parse_yaml(src: Path, rel: Path) -> Mapping[str, object]:
    """Parse a YAML file with ruamel.yaml, preserving source positions.

    On parse error, raises FileValidationError with a Diagnostic
    containing line/column from the YAML error mark.
    """
    try:
        data: Mapping[str, object] = _ruamel.load(  # type: ignore[no-untyped-call]
            src.read_text(encoding="utf-8")
        )
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise FileValidationError(
            diagnostics=[
                Diagnostic(
                    file=rel,
                    line=mark.line + 1 if mark else None,
                    column=mark.column + 1 if mark else None,
                    message=getattr(exc, "problem", None) or str(exc),
                    source="ruamel.yaml",
                )
            ]
        ) from exc
    return data


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
