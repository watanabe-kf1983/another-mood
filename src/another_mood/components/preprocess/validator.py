"""JSON Schema validator producing source-aware Diagnostics."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import jsonschema
import regex

from another_mood.components.preprocess.position_resolver import resolve_position
from another_mood.components.shared.diagnostic import Diagnostic


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
