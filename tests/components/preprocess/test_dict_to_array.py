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


class TestNonObjectAdditionalProperties:
    """additionalProperties with non-object type wraps values as {id, value}."""

    SCHEMA_STRING = _schema("""
        type: object
        additionalProperties:
          type: string
    """)

    SCHEMA_NUMBER = _schema("""
        type: object
        additionalProperties:
          type: number
    """)

    def test_string_values(self) -> None:
        data = _y("""
            en: English
            ja: Japanese
        """)
        result = normalize_data(data, self.SCHEMA_STRING)
        assert result == _y("""
            - id: en
              value: English
            - id: ja
              value: Japanese
        """)

    def test_number_values(self) -> None:
        data = _y("""
            width: 100
            height: 200
        """)
        result = normalize_data(data, self.SCHEMA_NUMBER)
        assert result == _y("""
            - id: width
              value: 100
            - id: height
              value: 200
        """)

    def test_empty_dict(self) -> None:
        assert normalize_data({}, self.SCHEMA_STRING) == []


class TestNestedNonObjectAdditionalProperties:
    """Non-object additionalProperties nested inside object properties."""

    SCHEMA = _schema("""
        type: object
        additionalProperties:
          type: object
          properties:
            name: { type: string }
            labels:
              type: object
              additionalProperties:
                type: string
          additionalProperties: false
          required: [name, labels]
    """)

    def test_normalizes_nested_scalar_dict(self) -> None:
        data = _y("""
            item1:
              name: Item
              labels:
                color: red
                size: large
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == _y("""
            - id: item1
              name: Item
              labels:
                - id: color
                  value: red
                - id: size
                  value: large
        """)


class TestNonObjectAdditionalPropertiesRecursion:
    """Non-object additionalProperties with nested structure recurses into value."""

    SCHEMA = _schema("""
        type: object
        additionalProperties:
          type: array
          items:
            type: object
            additionalProperties:
              type: object
              properties:
                label: { type: string }
              additionalProperties: false
    """)

    def test_recurses_into_array_value(self) -> None:
        data = _y("""
            group1:
              - tagA:
                  label: A
                tagB:
                  label: B
        """)
        result = normalize_data(data, self.SCHEMA)
        assert result == _y("""
            - id: group1
              value:
                - - id: tagA
                    label: A
                  - id: tagB
                    label: B
        """)


class TestNonObjectValues:
    """Scalar and non-object values pass through unchanged."""

    def test_string(self) -> None:
        assert normalize_data("hello", _schema("type: string")) == "hello"

    def test_number(self) -> None:
        assert normalize_data(42, _schema("type: number")) == 42

    def test_null(self) -> None:
        assert normalize_data(None, _schema("type: string")) is None
