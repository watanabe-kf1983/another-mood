"""Resolve YAML source positions from ruamel.yaml parsed data.

ruamel.yaml's CommentedMap/CommentedSeq carry .lc (LineCol) metadata
as Python attributes, invisible to JSON Schema validation and YAML
serialization.  This module provides a clean API to extract positions
given a data path (e.g. from jsonschema's ValidationError.absolute_path).

When the data lacks .lc metadata (e.g. plain dicts from non-ruamel
sources), resolve_position returns None instead of raising.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq  # type: ignore[attr-defined]

# ruamel.yaml's YAML.load() returns Any, and .lc / LineCol members lack
# type annotations.  We accept Any for root/node and access .lc via
# getattr to prevent Unknown propagation through pyright.


@dataclass(frozen=True)
class Position:
    """1-based source position."""

    line: int
    column: int


def resolve_position(
    path: Sequence[str | int],
    root: Any,
    *,
    identifier: str | None = None,
) -> Position | None:
    """Resolve the source position for a data path in a ruamel.yaml tree.

    path: sequence of keys/indices (e.g. ["schemas", "users", "type"]).
    root: parsed data — ruamel.yaml CommentedMap for positions, or plain
          dict/list (returns None).

    identifier: optional refinement — when given and the subtree at
        *path* is a dict that has *identifier* as one of its keys,
        return that key's position instead of the path-based one.
        Lets callers point a diagnostic at a quoted name from an error
        message (e.g. an unexpected key) instead of the less informative
        parent the data path resolves to.  Falls back to the path-based
        position when the subtree does not contain the identifier.
    """
    try:
        subtree, parent, last_step = _walk(path, root)
        return _path_position(subtree, parent, last_step, identifier)
    except (AttributeError, TypeError):
        return None


def _walk(path: Sequence[str | int], root: Any) -> tuple[Any, Any, object]:
    """Walk *path* down from *root*; return (subtree, parent, last_step).

    parent and last_step are None when *path* is empty (subtree is root)."""
    parent: Any = None
    last_step: object = None
    subtree: Any = root
    for step in path:
        parent, last_step, subtree = subtree, step, subtree[step]
    return subtree, parent, last_step


def _path_position(
    subtree: Any, parent: Any, last_step: object, identifier: str | None = None
) -> Position:
    """Position of subtree itself (path empty), of parent[last_step], or
    — when *identifier* is given and *subtree* is a map containing it —
    of *identifier* as a key inside subtree."""
    if (
        identifier is not None
        and isinstance(subtree, CommentedMap)
        and identifier in subtree
    ):
        self_lc = getattr(subtree, "lc")
        return _position(*self_lc.key(identifier))
    if isinstance(parent, CommentedMap) and isinstance(last_step, str):
        parent_lc = getattr(parent, "lc")
        return _position(*parent_lc.value(last_step))
    if isinstance(parent, CommentedSeq) and isinstance(last_step, int):
        parent_lc = getattr(parent, "lc")
        return _position(*parent_lc.item(last_step))
    if isinstance(subtree, (CommentedMap, CommentedSeq)):
        self_lc = getattr(subtree, "lc")
        return _position(self_lc.line, self_lc.col)
    raise TypeError(f"unexpected node {type(parent)} at step {last_step!r}")


def _position(line: Any, col: Any) -> Position:
    """ruamel.yaml's 0-based (line, col) → 1-based Position."""
    return Position(line=int(line) + 1, column=int(col) + 1)
