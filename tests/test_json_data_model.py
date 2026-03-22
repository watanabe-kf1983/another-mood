"""Tests for JSON data model — deep merge strategy."""

from typing import Any

from reqs_builder.json_data_model import deep_merge


class TestDeepMerge:
    def test_disjoint_keys(self) -> None:
        result = deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_objects_merged_recursively(self) -> None:
        base: dict[str, Any] = {"config": {"database": {"host": "localhost"}}}
        override: dict[str, Any] = {"config": {"database": {"port": 5432}}}

        result = deep_merge(base, override)
        assert result == {"config": {"database": {"host": "localhost", "port": 5432}}}

    def test_arrays_concatenated(self) -> None:
        base: dict[str, Any] = {"entities": [{"id": "user"}]}
        override: dict[str, Any] = {"entities": [{"id": "order"}]}

        result = deep_merge(base, override)
        assert result == {"entities": [{"id": "user"}, {"id": "order"}]}

    def test_scalars_later_wins(self) -> None:
        base: dict[str, Any] = {"config": {"database": {"host": "localhost"}}}
        override: dict[str, Any] = {"config": {"database": {"host": "production"}}}

        result = deep_merge(base, override)
        assert result == {"config": {"database": {"host": "production"}}}

    def test_empty_base(self) -> None:
        result = deep_merge({}, {"key": "value"})
        assert result == {"key": "value"}

    def test_empty_override(self) -> None:
        result = deep_merge({"key": "value"}, {})
        assert result == {"key": "value"}

    def test_both_empty(self) -> None:
        result = deep_merge({}, {})
        assert result == {}

    def test_does_not_mutate_inputs(self) -> None:
        base: dict[str, Any] = {"items": [1], "config": {"a": 1}}
        override: dict[str, Any] = {"items": [2], "config": {"b": 2}}
        base_copy: dict[str, Any] = {"items": [1], "config": {"a": 1}}
        override_copy: dict[str, Any] = {"items": [2], "config": {"b": 2}}

        deep_merge(base, override)
        assert base == base_copy
        assert override == override_copy
