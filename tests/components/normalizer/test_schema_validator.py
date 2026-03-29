"""Tests for schema_validator — SchemaSchema validation."""

from pathlib import Path

import pytest
import yaml

from reqs_builder.components.normalizer.schema_validator import (
    validate_schema_file,
    validate_schema_source,
)

_EXAMPLE_SCHEMA_DIR = Path("example-project/definition/schema")


# ── Helpers ──────────────────────────────────────────────────────────


def _valid(src: str) -> None:
    assert validate_schema_file(yaml.safe_load(src)) == []


def _invalid(src: str) -> None:
    assert len(validate_schema_file(yaml.safe_load(src))) > 0


# ── Example-project schemas ─────────────────────────────────────────


class TestExampleProjectSchemas:
    @pytest.mark.parametrize("name", ["entities", "relations"])
    def test_passes(self, name: str) -> None:
        data = yaml.safe_load((_EXAMPLE_SCHEMA_DIR / f"{name}.yaml").read_text())
        assert validate_schema_file(data) == []


# ── Valid patterns ───────────────────────────────────────────────────

_VALID_CASES = [
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


class TestValidSchemas:
    @pytest.mark.parametrize("src", _VALID_CASES)
    def test_accepted(self, src: str) -> None:
        _valid(src)


# ── Rejected patterns ───────────────────────────────────────────────

_REJECTED_CASES = [
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


class TestRejectedSchemas:
    @pytest.mark.parametrize("src", _REJECTED_CASES)
    def test_rejected(self, src: str) -> None:
        _invalid(src)


# ── validate_schema_source integration ────────────────────────────────


_DUMMY_FILE = Path("test.yaml")


class TestValidateSchemaSource:
    def test_error_has_position(self) -> None:
        src = (
            "schemas:\n"
            "  users:\n"
            "    type: 42\n"  # line 3 — invalid type value
        )
        errors = validate_schema_source(src, _DUMMY_FILE)
        assert len(errors) >= 1
        assert errors[0].line == 3
        assert errors[0].column is not None
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_valid_source_returns_empty(self) -> None:
        src = "schemas:\n  users:\n    type: object\n"
        assert validate_schema_source(src, _DUMMY_FILE) == []

    def test_non_mapping_source(self) -> None:
        src = "- just a list\n"
        errors = validate_schema_source(src, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_yaml_syntax_error(self) -> None:
        src = "a: [\n"
        errors = validate_schema_source(src, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].line is not None
        assert errors[0].source == "ruamel.yaml"
        assert errors[0].file == _DUMMY_FILE

    def test_yaml_duplicate_key(self) -> None:
        src = "schemas:\n  a:\n    type: object\n  a:\n    type: string\n"
        errors = validate_schema_source(src, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].source == "ruamel.yaml"
        assert "duplicate" in errors[0].message

    def test_example_project(self) -> None:
        path = _EXAMPLE_SCHEMA_DIR / "entities.yaml"
        src = path.read_text()
        assert validate_schema_source(src, path) == []
