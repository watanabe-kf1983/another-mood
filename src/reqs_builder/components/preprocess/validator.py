"""Validation infrastructure — parse YAML and validate against JSON Schema.

Provides shared building blocks used by both SchemaInspector and Normalizer:

* ``parse_yaml`` — parse YAML with ruamel.yaml, preserving source positions
  for line-accurate diagnostics.
* ``Validator`` — validate data against a JSON Schema,
  returning Diagnostic objects with line/column positions.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import jsonschema
from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from reqs_builder.components.preprocess.position_resolver import resolve_position
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_ruamel = YAML()


def parse_yaml(src: Path) -> Mapping[str, object]:
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
                    file=src,
                    line=mark.line + 1 if mark else None,
                    column=mark.column + 1 if mark else None,
                    message=getattr(exc, "problem", None) or str(exc),
                    source="ruamel.yaml",
                )
            ]
        ) from exc
    return data


class Validator:
    """JSON Schema validator that checks data against a JSON Schema object.

    Callers are responsible for loading/building the schema;
    Validator only handles validation and diagnostic conversion.
    """

    def __init__(self, schema: Mapping[str, object]) -> None:
        self._validator = jsonschema.Draft202012Validator(schema)

    def validate(self, data: Any, file: Path) -> Sequence[Diagnostic]:
        """Validate parsed data and return diagnostics.

        When *data* is a ruamel.yaml object (CommentedMap/CommentedSeq),
        diagnostics include line/column positions.  For plain dicts/lists,
        line and column are None.
        """
        return [
            _to_diagnostic(err, data, file)
            for err in self._validator.iter_errors(data)  # type: ignore[arg-type]
        ]

    def validate_yaml(self, src: Path) -> Sequence[Diagnostic]:
        """Parse a YAML file and validate against the schema.

        Combines parse_yaml and validate in one call.
        Returns parse error diagnostics instead of raising.
        """
        try:
            data = parse_yaml(src)
        except FileValidationError as exc:
            return exc.diagnostics
        return self.validate(data, src)


def _to_diagnostic(
    err: jsonschema.ValidationError, data: object, file: Path
) -> Diagnostic:
    # TODO: For additionalProperties errors, resolve_position points to the
    # parent object, not the unexpected key.  Extract the property name from
    # the error and look up its position in the CommentedMap for a precise line.
    pos = resolve_position(err.absolute_path, data)
    return Diagnostic(
        file=file,
        line=pos.line if pos else None,
        column=pos.column if pos else None,
        message=err.message,
        source="jsonschema",
    )
