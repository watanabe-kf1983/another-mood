"""Tests for SchemaInspector — SchemaSchema validation and data catalog extraction."""

from pathlib import Path

import pytest
import yaml

from another_mood.components.preprocess.schema_inspector import (
    build_schema_validator,
    check_schema,
    inspect_schema,
)
from another_mood.components.shared.diagnostic import FileValidationError


# ── build_schema_validator ──────────────────────────────────────────

_VALID_SCHEMA_CASES = [
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: string }
                email: { type: string }
              additionalProperties: false
              required: [name]
        additionalProperties: false
        """,
        id="dict pattern",
    ),
    pytest.param(
        """
        type: object
        properties:
          config:
            type: object
            properties:
              version: { type: string }
              debug: { type: boolean }
            additionalProperties: false
            required: [version]
        additionalProperties: false
        """,
        id="fixed structure",
    ),
    pytest.param(
        """
        type: object
        properties:
          items:
            type: array
            items:
              type: object
              properties:
                id: { type: string }
              additionalProperties: false
        additionalProperties: false
        """,
        id="array schema",
    ),
    pytest.param(
        """
        type: object
        properties:
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
        additionalProperties: false
        """,
        id="validation keywords passthrough",
    ),
    pytest.param(
        """
        type: object
        properties:
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
        additionalProperties: false
        """,
        id="metadata keywords",
    ),
    pytest.param(
        """
        type: object
        properties:
          エンティティ:
            type: object
            additionalProperties:
              type: object
              properties:
                名前: { type: string }
              additionalProperties: false
        additionalProperties: false
        """,
        id="unicode schema and property names",
    ),
]

_REJECTED_SCHEMA_CASES = [
    pytest.param(
        """
        type: object
        properties:
          users:
            $ref: "#/$defs/user"
        additionalProperties: false
        """,
        id="$ref rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            $defs:
              name: { type: string }
            type: object
        additionalProperties: false
        """,
        id="$defs rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            allOf:
              - type: object
        additionalProperties: false
        """,
        id="allOf rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            anyOf:
              - type: string
              - type: number
        additionalProperties: false
        """,
        id="anyOf rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            if: { type: string }
            then: { minLength: 1 }
        additionalProperties: false
        """,
        id="if/then/else rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            patternProperties:
              "^S_": { type: string }
        additionalProperties: false
        """,
        id="patternProperties rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            properties:
              version: { type: string }
            additionalProperties:
              type: object
              properties:
                name: { type: string }
              additionalProperties: false
        additionalProperties: false
        """,
        id="properties + additionalProperties as schema rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            properties:
              version: { type: string }
        additionalProperties: false
        """,
        id="properties without additionalProperties: false rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users: { type: object, additionalProperties: { type: string } }
        additionalProperties: false
        unknown_key: something
        """,
        id="unknown top-level key rejected",
    ),
    pytest.param(
        """
        type: object
        additionalProperties:
          type: object
          properties:
            name: { type: string }
          additionalProperties: false
        """,
        id="root dict pattern (additionalProperties as schema) rejected",
    ),
    pytest.param(
        """
        type: object
        additionalProperties: false
        """,
        id="root without properties rejected",
    ),
    pytest.param(
        """
        type: array
        items:
          type: object
          properties:
            id: { type: string }
          additionalProperties: false
        """,
        id="root non-object type rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          my-schema:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: string }
              additionalProperties: false
        additionalProperties: false
        """,
        id="hyphenated schema name rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            properties:
              first-name: { type: string }
            additionalProperties: false
        additionalProperties: false
        """,
        id="hyphenated property name rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                name: { type: [string, "null"] }
              additionalProperties: false
        additionalProperties: false
        """,
        id="array type rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                placeholder: { type: "null" }
              additionalProperties: false
        additionalProperties: false
        """,
        id="null type rejected",
    ),
    pytest.param(
        """
        type: object
        properties:
          users:
            type: object
            additionalProperties:
              type: object
              properties:
                phase: { enum: [1, 2, 3] }
              additionalProperties: false
        additionalProperties: false
        """,
        id="missing type on sub-property rejected",
    ),
    pytest.param(
        """
        properties:
          users: { type: object, additionalProperties: { type: string } }
        additionalProperties: false
        """,
        id="missing type on root rejected",
    ),
]


class TestBuildSchemaValidator:
    _validator = build_schema_validator()

    @pytest.mark.parametrize("src", _VALID_SCHEMA_CASES)
    def test_accepted(self, src: str) -> None:
        data = yaml.safe_load(src)
        assert self._validator.validate(data) == []

    @pytest.mark.parametrize("src", _REJECTED_SCHEMA_CASES)
    def test_rejected(self, src: str) -> None:
        data = yaml.safe_load(src)
        assert len(self._validator.validate(data)) > 0


# ── check_schema ────────────────────────────────────────────────────


def _write_schema(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


_VALID_SCHEMA_BODY = """\
type: object
properties:
  users:
    type: object
    additionalProperties:
      type: object
      properties:
        name: { type: string }
      additionalProperties: false
additionalProperties: false
"""

_INVALID_SCHEMA_BODY = """\
type: object
properties:
  items:
    type: object
    properties:
      name: { type: string }
    additionalProperties:
      type: object
additionalProperties: false
"""


class TestCheckSchema:
    """check_schema: validate schema files directly."""

    def test_valid_schema_passes(self, tmp_path: Path) -> None:
        f = _write_schema(tmp_path / "schema.yaml", _VALID_SCHEMA_BODY)
        check_schema(f)

    def test_invalid_schema_raises(self, tmp_path: Path) -> None:
        f = _write_schema(tmp_path / "schema.yaml", _INVALID_SCHEMA_BODY)
        with pytest.raises(FileValidationError) as exc_info:
            check_schema(f)
        assert len(exc_info.value.diagnostics) >= 1
        assert exc_info.value.diagnostics[0].file == f

    def test_broken_yaml_collected_as_diagnostic(self, tmp_path: Path) -> None:
        f = _write_schema(tmp_path / "schema.yaml", "a: [unterminated\n")
        with pytest.raises(FileValidationError) as exc_info:
            check_schema(f)
        assert exc_info.value.diagnostics[0].file == f
        assert exc_info.value.diagnostics[0].source == "ruamel.yaml"


# ── inspect_schema (component) ───────────────────────────────────────


class TestInspectSchema:
    """inspect_schema: pipeline component writes the data catalog."""

    def test_writes_user_schema_catalog(self, tmp_path: Path) -> None:
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(
            "type: object\n"
            "properties:\n"
            "  recipes:\n"
            "    type: object\n"
            "    additionalProperties:\n"
            "      type: object\n"
            "      properties:\n"
            "        title: { type: string }\n"
            "      additionalProperties: false\n"
            "additionalProperties: false\n"
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        inspect_schema.fn(schema_file, out_dir=out_dir)

        out_file = out_dir / "schema.yaml"
        assert out_file.exists()
        data = yaml.safe_load(out_file.read_text())
        entities = data["__definition"]["entities"]
        assert entities[0]["id"] == "recipes"

    def test_emits_builtin_prose_catalog(self, tmp_path: Path) -> None:
        """Built-in prose schema is emitted under __builtin/ so it shows up in meta-docs."""
        schema_file = _write_schema(tmp_path / "schema.yaml", _VALID_SCHEMA_BODY)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        inspect_schema.fn(schema_file, out_dir=out_dir)

        out_file = out_dir / "__builtin" / "content-schema.yaml"
        assert out_file.exists()
        data = yaml.safe_load(out_file.read_text())
        prose = next(e for e in data["__definition"]["entities"] if e["id"] == "prose")
        assert prose["builtin"] is True

    def test_emits_builtin_definition_catalog(self, tmp_path: Path) -> None:
        """Self-description catalog (__definition.*) is emitted under __builtin/.

        Each catalog dataclass contributes its own ``catalog()`` Node;
        ``inspect_schema`` flattens them under the ``__definition.*``
        namespace and tags every record ``builtin=True``.
        """
        schema_file = _write_schema(tmp_path / "schema.yaml", _VALID_SCHEMA_BODY)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        inspect_schema.fn(schema_file, out_dir=out_dir)

        out_file = out_dir / "__builtin" / "__definition.yaml"
        assert out_file.exists()
        data = yaml.safe_load(out_file.read_text())
        entities = data["__definition"]["entities"]
        assert {e["id"] for e in entities} == {
            "__definition.entities",
            "__definition.entities.item_type.attributes",
            "__definition.queries",
        }
        assert all(e["builtin"] for e in entities)
