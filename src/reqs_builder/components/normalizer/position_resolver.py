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

# ruamel.yaml's YAML.load() returns Any, so callers cannot pass
# a statically-typed CommentedMap.  We accept Any for root/node
# and rely on the runtime precondition (see module docstring).


@dataclass(frozen=True)
class Position:
    """1-based source position."""

    line: int
    column: int


def resolve_position(path: Sequence[str | int], root: Any) -> Position | None:
    """Resolve the source position for a data path in a ruamel.yaml tree.

    path: sequence of keys/indices (e.g. ["schemas", "users", "type"]).
    root: parsed data — ruamel.yaml CommentedMap for positions, or plain
          dict/list (returns None).
    """
    try:
        return _resolve(path, root)
    except (AttributeError, TypeError):
        return None


def _resolve(path: Sequence[str | int], root: Any) -> Position:
    if not path:
        return _node_position(root)

    steps = list(path)
    node: Any = root
    for step in steps[:-1]:
        node = node[step]

    last = steps[-1]
    if isinstance(node, CommentedMap) and isinstance(last, str):
        return _map_value_position(node, last)
    if isinstance(node, CommentedSeq) and isinstance(last, int):
        return _seq_item_position(node, last)

    raise TypeError(f"unexpected node type {type(node)} at path {steps}")


# ── LineCol → Position conversion ────────────────────────────────────
#
# ruamel.yaml's .lc attribute and LineCol members (.line, .col) lack
# type annotations, so we access .lc via getattr (returns Any) to
# prevent Unknown propagation through pyright.


def _node_position(node: Any) -> Position:
    """Position of the node itself."""
    lc = getattr(node, "lc")
    return Position(line=int(lc.line) + 1, column=int(lc.col) + 1)


def _map_value_position(node: CommentedMap, key: str) -> Position:
    """Position of a key's value."""
    lc = getattr(node, "lc")
    pos = lc.value(key)
    return Position(line=int(pos[0]) + 1, column=int(pos[1]) + 1)


def _seq_item_position(node: CommentedSeq, index: int) -> Position:
    """Position of a list item."""
    lc = getattr(node, "lc")
    pos = lc.item(index)
    return Position(line=int(pos[0]) + 1, column=int(pos[1]) + 1)
