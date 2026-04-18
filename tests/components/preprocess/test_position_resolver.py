"""Tests for position_resolver — YAML source position resolution."""

from typing import Any

import pytest
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from another_mood.components.preprocess.position_resolver import (
    Position,
    resolve_position,
)

_yaml = YAML()


def _load(src: str) -> Any:
    return _yaml.load(src)  # type: ignore[no-untyped-call]


class TestResolvePosition:
    def test_root_node(self) -> None:
        root = _load("key: value\n")
        assert resolve_position([], root) == Position(line=1, column=1)

    def test_map_value_string(self) -> None:
        root = _load("name: Alice\nage: 30\n")
        assert resolve_position(["name"], root) == Position(line=1, column=7)
        assert resolve_position(["age"], root) == Position(line=2, column=6)

    def test_nested_map(self) -> None:
        root = _load(
            "schemas:\n"  # line 1
            "  users:\n"  # line 2
            "    type: object\n"  # line 3, col 11
        )
        assert resolve_position(["schemas", "users", "type"], root) == Position(
            line=3, column=11
        )

    def test_seq_item(self) -> None:
        root = _load(
            "items:\n"
            "  - first\n"  # line 2, col 5
            "  - second\n"  # line 3, col 5
        )
        assert resolve_position(["items", 0], root) == Position(line=2, column=5)
        assert resolve_position(["items", 1], root) == Position(line=3, column=5)

    def test_nested_seq_map(self) -> None:
        root = _load(
            "references:\n"  # line 1
            "  - from: orders\n"  # line 2
            "    to: users\n"  # line 3, col 9
        )
        assert resolve_position(["references", 0, "to"], root) == Position(
            line=3, column=9
        )

    def test_deeply_nested(self) -> None:
        root = _load(
            "schemas:\n"  # line 1
            "  entities:\n"  # line 2
            "    type: array\n"  # line 3
            "    items:\n"  # line 4
            "      type: object\n"  # line 5
            "      properties:\n"  # line 6
            "        id:\n"  # line 7
            "          type: string\n"  # line 8, col 17
        )
        assert resolve_position(
            ["schemas", "entities", "items", "properties", "id", "type"], root
        ) == Position(line=8, column=17)

    def test_missing_key_raises(self) -> None:
        root = _load("name: Alice\n")
        with pytest.raises(KeyError):
            resolve_position(["missing"], root)

    def test_plain_dict_returns_none(self) -> None:
        assert resolve_position([], {"plain": "dict"}) is None

    def test_unexpected_node_type_returns_none(self) -> None:
        root = _load("key: value\n")
        # path ends with int but parent is a map
        assert resolve_position(["key", 0], root) is None


class TestResolvePositionWithIdentifier:
    """Identifier hint refines the path-based position via DFS search."""

    def test_found_in_nested_descendant(self) -> None:
        root = _load(
            "items:\n"  # line 1
            "  - from: a\n"  # line 2
            "    extra: b\n"  # line 3, col 5
        )
        assert resolve_position(["items"], root, identifier="extra") == Position(
            line=3, column=5
        )

    def test_not_found_falls_back_to_path_position(self) -> None:
        root = _load(
            "items:\n"  # line 1
            "  - from: a\n"  # line 2, col 5
        )
        assert resolve_position(["items", 0], root, identifier="missing") == Position(
            line=2, column=5
        )

    def test_picks_first_dfs_match(self) -> None:
        root = _load(
            "outer:\n"  # line 1
            "  bad: first\n"  # line 2, col 3 — direct key
            "  nested:\n"  # line 3
            "    bad: second\n"  # line 4 — also matches
        )
        assert resolve_position(["outer"], root, identifier="bad") == Position(
            line=2, column=3
        )
