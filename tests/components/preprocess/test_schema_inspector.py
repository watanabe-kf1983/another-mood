"""Tests for SchemaInspector — SchemaSchema validation and check_schema."""

from pathlib import Path

import pytest
import yaml

from reqs_builder.components.preprocess.schema_inspector import (
    build_schema_validator,
    check_schema,
)
from reqs_builder.components.shared.diagnostic import FileValidationError

_DUMMY_FILE = Path("test.yaml")


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
              additionalProperties: false
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
            additionalProperties: false
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
              additionalProperties: false
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
              additionalProperties: false
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
              additionalProperties: false
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
              additionalProperties: false
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
              additionalProperties: false
        """,
        id="properties + additionalProperties as schema rejected",
    ),
    pytest.param(
        """
        schemas:
          users:
            type: object
            properties:
              version: { type: string }
        """,
        id="properties without additionalProperties: false rejected",
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
        assert self._validator.validate(data, _DUMMY_FILE) == []

    @pytest.mark.parametrize("src", _REJECTED_SCHEMA_CASES)
    def test_rejected(self, src: str) -> None:
        data = yaml.safe_load(src)
        assert len(self._validator.validate(data, _DUMMY_FILE)) > 0


# ── check_schema ────────────────────────────────────────────────────


class TestCheckSchema:
    """check_schema: validate schema files directly."""

    def test_valid_schemas_pass(self, tmp_path: Path) -> None:
        f = tmp_path / "entities.yaml"
        f.write_text(
            "schemas:\n"
            "  users:\n"
            "    type: object\n"
            "    additionalProperties:\n"
            "      type: object\n"
            "      properties:\n"
            "        name: { type: string }\n"
            "      additionalProperties: false\n"
        )
        check_schema([f])

    def test_invalid_schema_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text(
            "schemas:\n"
            "  items:\n"
            "    type: object\n"
            "    properties:\n"
            "      name: { type: string }\n"
            "    additionalProperties:\n"
            "      type: object\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            check_schema([f])
        assert len(exc_info.value.diagnostics) >= 1
        assert exc_info.value.diagnostics[0].file == f

    def test_collects_errors_across_files(self, tmp_path: Path) -> None:
        good = tmp_path / "good.yaml"
        good.write_text(
            "schemas:\n"
            "  users:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        name: { type: string }\n"
            "      additionalProperties: false\n"
        )
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "schemas:\n"
            "  items:\n"
            "    type: object\n"
            "    properties:\n"
            "      name: { type: string }\n"
            "    additionalProperties:\n"
            "      type: object\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            check_schema([good, bad])
        files_with_errors = {d.file for d in exc_info.value.diagnostics}
        assert bad in files_with_errors
        assert good not in files_with_errors

    def test_broken_yaml_collected_as_diagnostic(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.yaml"
        f.write_text("a: [unterminated\n")
        with pytest.raises(FileValidationError) as exc_info:
            check_schema([f])
        assert exc_info.value.diagnostics[0].file == f
        assert exc_info.value.diagnostics[0].source == "ruamel.yaml"
