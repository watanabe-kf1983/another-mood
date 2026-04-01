"""Tests for validator — validate_data and validator builders."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from reqs_builder.components.preprocess.validator import (
    build_content_validator,
    build_schema_validator,
    validate_data,
)

_DUMMY_FILE = Path("test.yaml")
_ruamel = YAML()


def _ruamel_load(src: str) -> Any:
    return _ruamel.load(src)  # type: ignore[no-untyped-call]


# ── validate_data ───────────────────────────────────────────────────


class TestValidateData:
    """Core validation: Diagnostic conversion, position resolution."""

    _schema_validator = build_schema_validator()

    def test_ruamel_data_has_position(self) -> None:
        data = _ruamel_load("schemas:\n  users:\n    type: 42\n")
        errors = validate_data(data, _DUMMY_FILE, self._schema_validator)
        assert len(errors) >= 1
        assert errors[0].line == 3
        assert errors[0].column is not None
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_plain_dict_has_no_position(self) -> None:
        data = {"schemas": {"users": {"type": 42}}}
        errors = validate_data(data, _DUMMY_FILE, self._schema_validator)
        assert len(errors) >= 1
        assert errors[0].line is None
        assert errors[0].column is None

    def test_valid_data_returns_empty(self) -> None:
        data = _ruamel_load("schemas:\n  users:\n    type: object\n")
        assert validate_data(data, _DUMMY_FILE, self._schema_validator) == []

    def test_non_mapping(self) -> None:
        data = [{"just": "a list"}]
        errors = validate_data(data, _DUMMY_FILE, self._schema_validator)
        assert len(errors) == 1
        assert errors[0].source == "jsonschema"


# ── build_schema_validator ──────────────────────────────────────────

_VALID_SCHEMA_CASES = [
    pytest.param(
        """
        schemas:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: string }
                email: { type: string }
              required: [name]
        """,
        id="dict pattern",
    ),
    pytest.param(
        """
        schemas:
          config:
            type: object
            properties:
              version: { type: string }
              debug: { type: boolean }
            required: [version]
        """,
        id="fixed structure",
    ),
    pytest.param(
        """
        schemas:
          items:
            type: array
            items:
              type: object
              properties:
                id: { type: string }
        """,
        id="array schema",
    ),
    pytest.param(
        """
        references:
          - from: orders.customer
            to: users
        """,
        id="references only",
    ),
    pytest.param(
        """
        schemas:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: string }
        references:
          - from: orders.customer
            to: users
        """,
        id="schemas and references",
    ),
    pytest.param(
        """
        schemas:
          products:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: string, minLength: 1 }
                price: { type: number, minimum: 0, exclusiveMinimum: 0 }
                status: { type: string, enum: [active, archived] }
                tags:
                  type: array
                  items: { type: string }
                  minItems: 1
                  uniqueItems: true
              required: [name, price]
        """,
        id="validation keywords passthrough",
    ),
    pytest.param(
        """
        schemas:
          users:
            type: object
            title: User schema
            description: Defines user entities
            additionalProperties:
              type: object
              properties:
                name:
                  type: string
                  title: User name
                  default: anonymous
                  examples: [Alice, Bob]
        """,
        id="metadata keywords",
    ),
]

_REJECTED_SCHEMA_CASES = [
    pytest.param(
        """
        schemas:
          users:
            $ref: "#/$defs/user"
        """,
        id="$ref rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            $defs:
              name: { type: string }
            type: object
        """,
        id="$defs rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            allOf:
              - type: object
        """,
        id="allOf rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            anyOf:
              - type: string
              - type: number
        """,
        id="anyOf rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            if: { type: string }
            then: { minLength: 1 }
        """,
        id="if/then/else rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            type: object
            patternProperties:
              "^S_": { type: string }
        """,
        id="patternProperties rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            type: object
            properties:
              version: { type: string }
            additionalProperties:
              type: object
              properties:
                name: { type: string }
        """,
        id="properties + additionalProperties mutual exclusion",
    ),
    pytest.param(
        """
        schemas:
          users: { type: object }
        unknown_key: something
        """,
        id="unknown top-level key rejected",
    ),
    pytest.param(
        """
        references:
          - from: orders.customer
        """,
        id="references missing required field",
    ),
]


class TestBuildSchemaValidator:
    _validator = build_schema_validator()

    @pytest.mark.parametrize("src", _VALID_SCHEMA_CASES)
    def test_accepted(self, src: str) -> None:
        data = yaml.safe_load(src)
        assert list(self._validator.iter_errors(data)) == []

    @pytest.mark.parametrize("src", _REJECTED_SCHEMA_CASES)
    def test_rejected(self, src: str) -> None:
        data = yaml.safe_load(src)
        assert len(list(self._validator.iter_errors(data))) > 0


# ── build_content_validator ─────────────────────────────────────────


class TestBuildContentValidator:
    _validator = build_content_validator(
        yaml.safe_load("""
            items:
              type: array
              items:
                type: object
                properties:
                  id: { type: string }
                  name: { type: string }
                required: [id, name]
        """)
    )

    def test_valid(self) -> None:
        data = yaml.safe_load("items:\n  - id: a\n    name: Alice\n")
        assert validate_data(data, _DUMMY_FILE, self._validator) == []

    def test_invalid(self) -> None:
        data = yaml.safe_load("items:\n  - id: a\n")  # missing 'name'
        errors = validate_data(data, _DUMMY_FILE, self._validator)
        assert len(errors) >= 1
        assert "name" in errors[0].message
