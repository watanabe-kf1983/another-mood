"""Validation infrastructure — parse YAML and validate against JSON Schema.

Provides shared building blocks used by both SchemaInspector and Normalizer:

* ``parse_yaml`` — parse YAML with ruamel.yaml, preserving source positions
  for line-accurate diagnostics.
* ``Validator`` — validate data against a JSON Schema,
  returning Diagnostic objects with line/column positions.
* ``UserStr`` / ``Location`` — user-input strings tagged with their source
  location, used by downstream identifier-integrity checks.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import regex
from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from another_mood.components.preprocess.position_resolver import (
    Position,
    resolve_position,
)
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError


@dataclass(frozen=True)
class Location:
    """Source location of a user-input value, including its file."""

    file: Path
    position: Position


class UserStr(str):
    """A string from user input, tagged with its source ``Location``.

    Drop-in for ``str`` (``isinstance``, equality, and hashing all behave
    identically), so call sites that don't care about provenance can keep
    treating it as a plain string.

    ``str`` is immutable, so the value must be set in ``__new__``; ``str``
    methods (``upper``, ``+``, slicing) return plain ``str`` and drop the
    location, so callers that want to preserve provenance must avoid string
    operations.  Identifier checks here only do ``==`` and dict lookup,
    which leave the original ``UserStr`` instance intact.
    """

    __slots__ = ("location",)
    location: Location

    def __new__(cls, value: str, location: Location) -> "UserStr":
        instance = super().__new__(cls, value)
        instance.location = location
        return instance


def parse_yaml(src: Path) -> Mapping[str, object]:
    """Parse a YAML file with ruamel.yaml, preserving source positions.

    On parse error, raises FileValidationError with a Diagnostic
    containing line/column from the YAML error mark.

    Uses a fresh YAML instance per call because ruamel.yaml's YAML()
    is not thread-safe (see components/shared/json_data_model.py).
    """
    try:
        data: Mapping[str, object] = YAML().load(  # type: ignore[no-untyped-call]
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


def _pattern_with_unicode(
    validator: jsonschema.Draft202012Validator,
    patrn: str,
    instance: object,
    schema: object,
) -> Any:
    """Pattern validator using ``regex`` module for Unicode property support.

    Replaces the default ``re``-based pattern validator so that
    ECMA 262 Unicode property escapes (e.g. ``\\p{L}``) work correctly.
    """
    if isinstance(instance, str) and not regex.search(patrn, instance):
        yield jsonschema.ValidationError(f"{instance!r} does not match {patrn!r}")


_UnicodeValidator: type[jsonschema.Draft202012Validator] = jsonschema.validators.extend(  # type: ignore[assignment]
    jsonschema.Draft202012Validator,
    validators={"pattern": _pattern_with_unicode},
)


class Validator:
    """JSON Schema validator that checks data against a JSON Schema object.

    Callers are responsible for loading/building the schema;
    Validator only handles validation and diagnostic conversion.
    """

    def __init__(self, schema: Mapping[str, object]) -> None:
        self._validator = _UnicodeValidator(schema)

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
    pos = resolve_position(
        err.absolute_path, data, identifier=_subject_identifier(err.message)
    )
    return Diagnostic(
        file=file,
        line=pos.line if pos else None,
        column=pos.column if pos else None,
        message=err.message,
        source="jsonschema",
    )


_SUBJECT_PATTERN = regex.compile(r"'([^']+)'")


def _subject_identifier(message: str) -> str | None:
    """The identifier the jsonschema error is about — an unexpected key,
    a missing required key, etc.

    jsonschema quotes this identifier in the message.  We extract it as
    a hint to point the diagnostic at where the name actually appears
    in the YAML, falling back to the parent location when it does not
    exist there.
    """
    match = _SUBJECT_PATTERN.search(message)
    return match.group(1) if match else None
