"""Source loader — parse user input files (YAML / Markdown) into data.

Concentrates the "user file → data" responsibility shared by every
preprocess pipeline:

* ``parse_yaml`` — parse a YAML file with ruamel.yaml, tagging scalar
  string values with a ``Location`` so downstream identifier-integrity
  checks can point diagnostics back at the originating YAML position.
* ``load_source`` — dispatch by file type and return data ready for
  schema validation.  Markdown files are wrapped raw (path-derived
  ``id`` + ``body``); interpreting the body (e.g. title from the H1)
  is left to ``preprocess.prose``.
* ``UserStr`` / ``Location`` — value type for user-input strings tagged
  with their source location.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # type: ignore[attr-defined]

from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)
from another_mood.components.shared.file_type import FileType


@dataclass(frozen=True)
class Location:
    """Source location (file + 1-based line/column) of a user-input value."""

    file: Path
    line: int
    column: int


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

    def __reduce__(self) -> tuple[type["UserStr"], tuple[str, Location]]:
        # Tells copy.deepcopy / pickle how to reconstruct, so UserStr
        # round-trips through dataclasses.asdict() and similar.
        return (UserStr, (str(self), self.location))


def load_source(src: Path, src_dir: Path) -> Mapping[str, object] | None:
    """Parse a source file into data, or None if the file type is not recognized."""
    if FileType.MARKDOWN.match(src):
        return load_prose(src, src_dir, mime_type="text/markdown")
    if FileType.YAML.match(src):
        return parse_yaml(src)
    return None


# ── YAML ───────────────────────────────────────────────────────────


def parse_yaml(src: Path) -> Mapping[str, object]:
    """Parse a YAML file with ruamel.yaml.

    Scalar strings are wrapped as ``UserStr`` carrying their source
    ``Location`` so downstream diagnostics can point back at the
    originating YAML position. Dict keys are not wrapped.

    Empty (or whitespace-only) files load as ``{}``. A non-mapping
    root (sequence, scalar) or a YAML parse error raises
    FileValidationError with line/column.
    """
    try:
        # Fresh YAML() per call: caching at module scope is not safe
        # because ruamel's YAML() shares mutable internal state across
        # invocations (see components/shared/json_data_model.py).
        loaded = YAML().load(  # type: ignore[no-untyped-call]
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
    if isinstance(loaded, Mapping):
        data = cast(Mapping[str, object], loaded)
        _tag_user_strings(data, src)
        return data
    elif loaded is None:
        return {}
    else:
        raise FileValidationError(
            diagnostics=[
                Diagnostic(
                    file=src,
                    line=1,
                    column=1,
                    message=(
                        f"Expected a YAML mapping at the root, "
                        f"got {type(loaded).__name__}"
                    ),
                    source="ruamel.yaml",
                )
            ]
        )


def _tag_user_strings(node: object, file: Path) -> None:
    """Walk a ruamel tree, replacing scalar str values with ``UserStr`` in place.

    Dict keys and non-string scalars are left untouched.
    """
    for container, key, value, lc_pos in _ruamel_children(node):
        if isinstance(value, str) and not isinstance(value, UserStr):
            container[key] = UserStr(value, _location(file, *lc_pos))
        else:
            _tag_user_strings(value, file)


def _ruamel_children(
    node: object,
) -> Iterator[tuple[Any, Any, Any, tuple[Any, Any]]]:
    """Yield (container, key_or_index, value, lc_position) for each child.

    Concentrates the ruamel-specific introspection — ``.lc.value`` /
    ``.lc.item`` are not in ruamel's type stubs, so the caller can stay
    free of typing escape hatches.
    """
    if isinstance(node, CommentedMap):
        lc = getattr(node, "lc")
        for key in list(node):  # type: ignore[no-untyped-call]
            yield node, key, node[key], lc.value(key)
    elif isinstance(node, CommentedSeq):
        lc = getattr(node, "lc")
        for i in range(len(node)):
            yield node, i, node[i], lc.item(i)


def _location(file: Path, line: Any, col: Any) -> Location:
    return Location(file=file, line=int(line) + 1, column=int(col) + 1)


# ── Prose ──────────────────────────────────────────────────────────


def load_prose(src: Path, src_dir: Path, *, mime_type: str) -> Mapping[str, object]:
    """Wrap a prose source file into a single ``prose`` record.

    The ``id`` is the source path relative to ``src_dir`` without its
    extension; the raw text becomes the record ``body``.  The body is
    left uninterpreted — deriving fields like ``title`` from it is the
    job of ``preprocess.prose``.
    """
    rel = src.relative_to(src_dir)
    return {
        "prose": [
            {
                "id": rel.with_suffix("").as_posix(),
                "body": {
                    "mime_type": mime_type,
                    "content": src.read_text(encoding="utf-8"),
                },
            }
        ]
    }
