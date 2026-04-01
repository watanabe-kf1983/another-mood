"""Tests for SchemaInspector — SchemaSchema validation and inspect_schema logic."""

from pathlib import Path

import pytest
import yaml

from reqs_builder.components.preprocess.schema_inspector import (
    build_schema_validator,
    inspect_schema,
)

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


# ── inspect_schema (Component wrapper) ──────────────────────────────


class TestInspectSchema:
    """inspect_schema: end-to-end through Component wrapper."""

    def test_valid_schemas_pass(self, tmp_path: Path) -> None:
        schema_dir = tmp_path / "schema"
        schema_dir.mkdir()
        (schema_dir / "entities.yaml").write_text(
            "schemas:\n"
            "  users:\n"
            "    type: object\n"
            "    additionalProperties:\n"
            "      type: object\n"
            "      properties:\n"
            "        name: { type: string }\n"
        )
        out = tmp_path / "out"
        inspect_schema(schema_dir=schema_dir, out_dir=out)

        # No error report (stage name not set in direct call)
        assert not (out / "__build_report.yaml").exists()

    def test_invalid_schema_writes_error_report(self, tmp_path: Path) -> None:
        schema_dir = tmp_path / "schema"
        schema_dir.mkdir()
        # properties + additionalProperties is mutually exclusive
        (schema_dir / "bad.yaml").write_text(
            "schemas:\n"
            "  items:\n"
            "    type: object\n"
            "    properties:\n"
            "      name: { type: string }\n"
            "    additionalProperties:\n"
            "      type: object\n"
        )
        out = tmp_path / "out"
        inspect_schema(schema_dir=schema_dir, out_dir=out)

        report = yaml.safe_load((out / "__build_report.yaml").read_text())
        assert report["__build_report"]["errors"]
        assert report["__build_report"]["diagnostics"]
        diag = report["__build_report"]["diagnostics"][0]
        assert "bad.yaml" in diag["file"]

    def test_collects_errors_across_files(self, tmp_path: Path) -> None:
        schema_dir = tmp_path / "schema"
        schema_dir.mkdir()
        (schema_dir / "good.yaml").write_text(
            "schemas:\n"
            "  users:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        name: { type: string }\n"
        )
        # properties + additionalProperties is mutually exclusive
        (schema_dir / "bad.yaml").write_text(
            "schemas:\n"
            "  items:\n"
            "    type: object\n"
            "    properties:\n"
            "      name: { type: string }\n"
            "    additionalProperties:\n"
            "      type: object\n"
        )
        out = tmp_path / "out"
        inspect_schema(schema_dir=schema_dir, out_dir=out)

        report = yaml.safe_load((out / "__build_report.yaml").read_text())
        diag_files = [d["file"] for d in report["__build_report"]["diagnostics"]]
        assert any("bad.yaml" in f for f in diag_files)
        assert not any("good.yaml" in f for f in diag_files)
