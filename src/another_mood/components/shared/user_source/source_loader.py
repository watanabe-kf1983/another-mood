"""Source loader — parse user input files (YAML / Markdown) into data.

Concentrates the "user file → data" responsibility shared by every
preprocess pipeline:

* ``parse_yaml`` — parse a YAML file with ruamel.yaml, tagging mapping
  keys and scalar string values with a ``Location`` so downstream
  identifier-integrity checks can point diagnostics back at the
  originating YAML position.
* ``load_source`` — dispatch by file type and return data ready for
  schema validation.  Markdown files are wrapped raw (path-derived
  ``id`` + ``body``); interpreting the body (e.g. title from the H1)
  is left to ``preprocess.prose``.
* ``UserStr`` / ``Location`` — value type for user-input strings tagged
  with their source location.
"""

import unicodedata
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


def _read_text_nfc(src: Path) -> str:
    """Decode ``src`` as UTF-8 and fold to NFC at this input boundary.

    Decode is a reversible bijection; NFC is a separate, non-invertible
    fold, so it can't ride on the decoder's options. Normalizing here
    keeps ids that differ only in canonical form from silently colliding
    on a form-insensitive filesystem (macOS). NFKC is unusable — its
    compatibility decomposition (``①`` → ``1``) would distort ids.
    """
    return unicodedata.normalize("NFC", src.read_text(encoding="utf-8"))


# ── YAML ───────────────────────────────────────────────────────────


def parse_yaml(src: Path) -> Mapping[str, object]:
    """Parse a YAML file with ruamel.yaml.

    Mapping keys and scalar string values are wrapped as ``UserStr``
    carrying their source ``Location`` so downstream diagnostics can
    point back at the originating YAML position.

    Empty (or whitespace-only) files load as ``{}``. A non-mapping
    root (sequence, scalar) or a YAML parse error raises
    FileValidationError with line/column.
    """
    try:
        # Fresh YAML() per call: caching at module scope is not safe
        # because ruamel's YAML() shares mutable internal state across
        # invocations (see components/shared/json_data_model.py).
        loaded = YAML().load(  # type: ignore[no-untyped-call]
            _read_text_nfc(src)
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
        tagged = _tag_mapping(cast(CommentedMap, loaded), src)
        return cast(Mapping[str, object], tagged)
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


def _tag_mapping(node: CommentedMap, file: Path) -> CommentedMap:
    for key, value, key_lc, value_lc in _map_children(node):
        # Delete first: re-assigning an equal key keeps the old key object.
        del node[key]
        node[_tag_value(key, file, key_lc)] = _tag_value(value, file, value_lc)
    return node


def _tag_sequence(node: CommentedSeq, file: Path) -> CommentedSeq:
    # Lists have no key to swap, so tag items in place (keeps their .lc).
    for i, value, item_lc in _seq_children(node):
        node[i] = _tag_value(value, file, item_lc)
    return node


def _tag_value(value: object, file: Path, lc_pos: tuple[Any, Any]) -> object:
    """Return the tagged form of a node at ``lc_pos``: recurse into a
    container, wrap a plain string as ``UserStr``, else leave it as is."""
    if isinstance(value, CommentedMap):
        return _tag_mapping(value, file)
    elif isinstance(value, CommentedSeq):
        return _tag_sequence(value, file)
    elif isinstance(value, str) and not isinstance(value, UserStr):
        return UserStr(value, _location(file, *lc_pos))
    else:
        return value


def _map_children(node: CommentedMap) -> Iterator[tuple[Any, Any, Any, Any]]:
    """Yield (key, value, key_lc, value_lc) per entry.

    Concentrates the ruamel-specific introspection — ``.lc.key`` /
    ``.lc.value`` are not in ruamel's type stubs — behind an ``Any``
    boundary so callers stay free of typing escape hatches.
    """
    lc = getattr(node, "lc")
    for key in list(node):  # type: ignore[no-untyped-call]
        yield key, node[key], lc.key(key), lc.value(key)


def _seq_children(node: CommentedSeq) -> Iterator[tuple[int, Any, Any]]:
    """Yield (index, value, item_lc) per element (see ``_map_children``)."""
    lc = getattr(node, "lc")
    for i in range(len(node)):
        yield i, node[i], lc.item(i)


def _location(file: Path, line: Any, col: Any) -> Location:
    return Location(file=file, line=int(line) + 1, column=int(col) + 1)


# ── Prose ──────────────────────────────────────────────────────────


def load_prose(src: Path, src_dir: Path, *, mime_type: str) -> Mapping[str, object]:
    """Wrap a prose source file into a single ``prose`` record.

    The ``id`` is the source path relative to ``src_dir`` without its
    extension; the raw text becomes the record ``body``.  The body is
    left uninterpreted — deriving fields like ``title`` from it is the
    job of ``preprocess.prose``.

    The ``id`` comes from the traversed filename, which never passes
    through the decoder, so it is NFC-folded separately here (see
    ``_read_text_nfc`` for why).
    """
    rel = src.relative_to(src_dir)
    return {
        "prose": [
            {
                "id": unicodedata.normalize("NFC", rel.with_suffix("").as_posix()),
                "body": {
                    "mime_type": mime_type,
                    "content": _read_text_nfc(src),
                },
            }
        ]
    }
