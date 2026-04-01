"""Tests for validator — validate_source and validator builders."""

from pathlib import Path

import pytest
import yaml

from reqs_builder.components.normalizer.validator import (
    build_content_validator,
    build_schema_validator,
    validate_source,
)

_DUMMY_FILE = Path("test.yaml")


# ── validate_source ─────────────────────────────────────────────────


class TestValidateSource:
    """Core validation: YAML parsing, position resolution, Diagnostic conversion."""

    _schema_validator = build_schema_validator()

    def test_error_has_position(self) -> None:
        src = (
            "schemas:\n"
            "  users:\n"
            "    type: 42\n"  # line 3 — invalid type value
        )
        errors = validate_source(src, _DUMMY_FILE, self._schema_validator)
        assert len(errors) >= 1
        assert errors[0].line == 3
        assert errors[0].column is not None
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_valid_source_returns_empty(self) -> None:
        src = "schemas:\n  users:\n    type: object\n"
        assert validate_source(src, _DUMMY_FILE, self._schema_validator) == []

    def test_non_mapping_source(self) -> None:
        src = "- just a list\n"
        errors = validate_source(src, _DUMMY_FILE, self._schema_validator)
        assert len(errors) == 1
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_yaml_syntax_error(self) -> None:
        src = "a: [\n"
        errors = validate_source(src, _DUMMY_FILE, self._schema_validator)
        assert len(errors) == 1
        assert errors[0].line is not None
        assert errors[0].source == "ruamel.yaml"
        assert errors[0].file == _DUMMY_FILE

    def test_yaml_duplicate_key(self) -> None:
        src = "schemas:\n  a:\n    type: object\n  a:\n    type: string\n"
        errors = validate_source(src, _DUMMY_FILE, self._schema_validator)
        assert len(errors) == 1
        assert errors[0].source == "ruamel.yaml"
        assert "duplicate" in errors[0].message


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
            config:
              type: object
              properties:
                version: { type: string }
              required: [version]
        """)
    )

    def test_valid(self) -> None:
        src = "items:\n  - id: a\n    name: Alice\n"
        assert validate_source(src, _DUMMY_FILE, self._validator) == []

    def test_invalid(self) -> None:
        src = "items:\n  - id: a\n"  # missing 'name'
        errors = validate_source(src, _DUMMY_FILE, self._validator)
        assert len(errors) >= 1
        assert "name" in errors[0].message
