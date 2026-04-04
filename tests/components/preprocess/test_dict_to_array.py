"""Tests for dict-to-array normalization (additionalProperties pattern)."""

from collections.abc import Mapping
from typing import cast

from ruamel.yaml import YAML

from reqs_builder.components.preprocess.dict_to_array import Schema, normalize_data

_yaml = YAML()


def _y(text: str) -> object:
    return _yaml.load(text)  # type: ignore[reportUnknownMemberType]


def _schema(text: str) -> Schema:
    return cast(Mapping[str, object], _yaml.load(text))  # type: ignore[reportUnknownMemberType]


class TestFlatDict:
    """Top-level additionalProperties: dict keys become id fields."""

    SCHEMA = _schema("""
        type: object
        additionalProperties:
          type: object
          properties:
            name: { type: string }
          additionalProperties: false
          required: [name]
    """)

    def test_converts_dict_to_array_with_id(self) -> None:
        data = _y("""
            alice:
              name: Alice
            bob:
              name: Bob
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == _y("""
            - id: alice
              name: Alice
            - id: bob
              name: Bob
        """)

    def test_preserves_key_order(self) -> None:
        data = _y("""
            z:
              name: Z
            a:
              name: A
        """)
        result = normalize_data(data, self.SCHEMA)
        assert [item["id"] for item in result] == ["z", "a"]  # type: ignore[union-attr]

    def test_empty_dict(self) -> None:
        assert normalize_data({}, self.SCHEMA) == []


class TestNestedDict:
    """Recursive normalization for nested additionalProperties."""

    SCHEMA = _schema("""
        type: object
        additionalProperties:
          type: object
          properties:
            name: { type: string }
            fields:
              type: object
              additionalProperties:
                type: object
                properties:
                  type: { type: string }
                additionalProperties: false
                required: [type]
          additionalProperties: false
          required: [name, fields]
    """)

    def test_normalizes_recursively(self) -> None:
        data = _y("""
            user:
              name: User
              fields:
                email:
                  type: string
                age:
                  type: number
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == _y("""
            - id: user
              name: User
              fields:
                - id: email
                  type: string
                - id: age
                  type: number
        """)


class TestFixedObject:
    """properties-only objects are left untouched."""

    SCHEMA = _schema("""
        type: object
        properties:
          name: { type: string }
          count: { type: number }
        additionalProperties: false
    """)

    def test_passes_through(self) -> None:
        data = _y("""
            name: Alice
            count: 3
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == {"name": "Alice", "count": 3}


class TestArrayItems:
    """Arrays with items schema: normalize each element."""

    SCHEMA = _schema("""
        type: array
        items:
          type: object
          properties:
            name: { type: string }
            tags:
              type: object
              additionalProperties:
                type: object
                properties:
                  label: { type: string }
                additionalProperties: false
          additionalProperties: false
    """)

    def test_normalizes_dict_inside_array_items(self) -> None:
        data = _y("""
            - name: item1
              tags:
                important:
                  label: Important
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == _y("""
            - name: item1
              tags:
                - id: important
                  label: Important
        """)


class TestNonObjectValues:
    """Scalar and non-object values pass through unchanged."""

    def test_string(self) -> None:
        assert normalize_data("hello", _schema("type: string")) == "hello"

    def test_number(self) -> None:
        assert normalize_data(42, _schema("type: number")) == 42

    def test_null(self) -> None:
        assert normalize_data(None, _schema("type: string")) is None
