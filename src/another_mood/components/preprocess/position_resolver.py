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

    identifier: optional refinement — when given, search the subtree at
        *path* for a CommentedMap that has *identifier* as one of its
        keys (DFS, first match wins) and prefer that key's position
        over the path-based result.  Lets callers point a diagnostic
        at a quoted name from an error message (e.g. an unexpected key)
        instead of the less informative parent the data path resolves
        to.  Falls back to the path-based position when the identifier
        is not found in the subtree.
    """
    try:
        subtree, parent, last_step = _walk(path, root)
        base = _path_position(subtree, parent, last_step)
        return _refine_with_identifier(base, subtree, identifier)
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


def _path_position(subtree: Any, parent: Any, last_step: object) -> Position:
    """Position of subtree itself (path empty) or of parent[last_step]."""
    if parent is None:
        lc = getattr(subtree, "lc")
        return _position(lc.line, lc.col)
    lc = getattr(parent, "lc")
    if isinstance(parent, CommentedMap) and isinstance(last_step, str):
        return _position(*lc.value(last_step))
    if isinstance(parent, CommentedSeq) and isinstance(last_step, int):
        return _position(*lc.item(last_step))
    raise TypeError(f"unexpected node {type(parent)} at step {last_step!r}")


def _refine_with_identifier(
    base: Position, subtree: Any, identifier: str | None
) -> Position:
    if identifier is None:
        return base
    return _search_key(subtree, identifier) or base


def _search_key(node: Any, identifier: str) -> Position | None:
    """DFS for the first CommentedMap that has *identifier* as a key."""
    if isinstance(node, CommentedMap):
        if identifier in node:
            lc = getattr(node, "lc")
            return _position(*lc.key(identifier))
        children: list[Any] = list(node.values())  # type: ignore[arg-type]
    elif isinstance(node, CommentedSeq):
        children = list(node)  # type: ignore[arg-type]
    else:
        return None
    for child in children:
        pos = _search_key(child, identifier)
        if pos is not None:
            return pos
    return None


def _position(line: Any, col: Any) -> Position:
    """ruamel.yaml's 0-based (line, col) → 1-based Position."""
    return Position(line=int(line) + 1, column=int(col) + 1)
