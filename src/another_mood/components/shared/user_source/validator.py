"""JSON Schema validator.

Returns ``ValidationIssue`` records — line/column/message/source without
a file binding.  Callers attach the file via ``ValidationIssue.at_file``
to produce a ``Diagnostic``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import jsonschema
import regex
from jsonschema.exceptions import best_match  # type: ignore[reportUnknownVariableType]

from another_mood.components.shared.user_source.position_resolver import (
    resolve_position,
)
from another_mood.components.shared.user_source.diagnostic import Diagnostic


@dataclass(frozen=True)
class ValidationIssue:
    """A schema-validation finding, without a file binding.

    Validator does not know which file the data came from, so it cannot
    build a full ``Diagnostic`` itself.  Callers turn an issue into a
    Diagnostic by attaching the file via :meth:`at_file`.
    """

    line: int | None
    column: int | None
    message: str
    source: str

    def at_file(self, file: Path) -> Diagnostic:
        return Diagnostic(
            file=file,
            line=self.line,
            column=self.column,
            message=self.message,
            source=self.source,
        )


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
    Validator only handles validation and issue conversion.
    """

    def __init__(self, schema: Mapping[str, object]) -> None:
        self._validator = _UnicodeValidator(schema)

    def validate(self, data: Any) -> Sequence[ValidationIssue]:
        """Validate parsed data and return issues.

        When *data* is a ruamel.yaml object (CommentedMap/CommentedSeq),
        issues include line/column positions.  For plain dicts/lists,
        line and column are None.
        """
        return [
            _to_issue(err, data)
            for err in self._validator.iter_errors(data)  # type: ignore[arg-type]
        ]


def _to_issue(err: jsonschema.ValidationError, data: object) -> ValidationIssue:
    # For anyOf/oneOf failures, the top-level message degrades to
    # "... not valid under any of the given schemas" with a full instance
    # dump; descend err.context to surface the actual cause.
    err = cast(jsonschema.ValidationError, best_match([err]))
    pos = resolve_position(
        err.absolute_path, data, identifier=_subject_identifier(err.message)
    )
    return ValidationIssue(
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
