"""Tests for content_normalizer."""

from pathlib import Path

import yaml

from another_mood.components.preprocess.content_normalizer import (
    build_contents_schema,
    normalize_contents,
)


class TestBuildContentsSchema:
    """build_contents_schema: merge built-in prose + user schema."""

    def test_merges_builtin_and_user_schema(self, tmp_path: Path) -> None:
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(
            "type: object\n"
            "properties:\n"
            "  entities:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        id: { type: string }\n"
            "      required: [id]\n"
            "additionalProperties: false\n"
        )
        schema = build_contents_schema(schema_file)

        from another_mood.components.preprocess.validator import Validator

        validator = Validator(schema)

        # User schema: entities validated
        issues = validator.validate({"entities": [{"id": 123}]})
        assert len(issues) >= 1

        # Built-in prose schema: prose validated
        issues = validator.validate(
            {
                "prose": [
                    {
                        "id": "doc",
                        "body": {"mime_type": "text/markdown", "content": "x"},
                    }
                ]
            }
        )
        assert issues == []

    def test_missing_schema_file_uses_builtin_only(self, tmp_path: Path) -> None:
        schema = build_contents_schema(tmp_path / "missing.yaml")

        from another_mood.components.preprocess.validator import Validator

        validator = Validator(schema)
        # prose still validated
        issues = validator.validate(
            {
                "prose": [
                    {
                        "id": "doc",
                        "body": {"mime_type": "text/markdown", "content": "x"},
                    }
                ]
            }
        )
        assert issues == []


class TestNormalizeContents:
    """normalize_contents: component smoke test."""

    def test_validates_and_writes(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("items:\n  - name: a\n")
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(
            "type: object\n"
            "properties:\n"
            "  items:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "additionalProperties: false\n"
        )

        out = tmp_path / "normalized"
        catalog_dir = tmp_path / "catalog"
        catalog_dir.mkdir()
        normalize_contents(
            src_dir=src,
            out_dir=out,
            schema_file=schema_file,
            data_catalog_dir=catalog_dir,
        )

        assert yaml.safe_load((out / "data" / "data.yaml.yaml").read_text()) == {
            "items": [{"name": "a"}]
        }
