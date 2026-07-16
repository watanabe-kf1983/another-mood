"""Tests for content_normalizer."""

from pathlib import Path
from textwrap import dedent

import yaml

from another_mood.components.preprocess.content_normalizer import (
    build_contents_schema,
    normalize_contents,
)
from another_mood.components.preprocess.schema_inspector import inspect_schema
from another_mood.components.shared.user_source.diagnostic import (
    DiagnosticReporter,
    DiagnosticSeverity,
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

        from another_mood.components.shared.user_source.validator import Validator

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

        from another_mood.components.shared.user_source.validator import Validator

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


# x-ref schema reused by the FK integration tests: albums.artist_id → artists.
_FK_SCHEMA = """
    type: object
    additionalProperties: false
    properties:
      artists:
        type: object
        additionalProperties:
          type: object
          additionalProperties: false
          properties:
            name: { type: string }
          required: [name]
      albums:
        type: object
        additionalProperties:
          type: object
          additionalProperties: false
          properties:
            title: { type: string }
            artist_id:
              type: string
              x-ref:
                entity: artists
          required: [title, artist_id]
"""


def test_normalize_contents_reports_dangling_fk_as_warning(tmp_path: Path) -> None:
    """End-to-end: inspect_schema's catalog + dangling FK → warning via reporter.

    Uses ``.fn(...)`` so the test can pass a :class:`DiagnosticReporter`
    explicitly (the Component-framework would otherwise inject one).
    """
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(dedent(_FK_SCHEMA).lstrip("\n"))
    src = tmp_path / "contents"
    src.mkdir()
    (src / "data.yaml").write_text(
        dedent("""
            artists:
              miyavi:
                name: Miyavi
            albums:
              a1:
                title: Day 1
                artist_id: ghost
        """).lstrip("\n")
    )
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    inspect_schema.fn(schema_file, out_dir=catalog_dir)
    out = tmp_path / "normalized"
    out.mkdir()

    reporter = DiagnosticReporter()
    normalize_contents.fn(
        src_dir=src,
        out_dir=out,
        schema_file=schema_file,
        data_catalog_dir=catalog_dir,
        reporter=reporter,
    )

    assert [(d.source, d.severity, d.message) for d in reporter.diagnostics] == [
        (
            "x-ref-data",
            DiagnosticSeverity.warning,
            "x-ref albums.artist_id = 'ghost' has no match in artists.id",
        ),
    ]
    # The normalized data still lands on disk — warnings do not stop the stage.
    assert (out / "data.yaml.yaml").exists()


# x-ref schema for the blob FK integration test: albums.jacket → blob.
_BLOB_FK_SCHEMA = """
    type: object
    additionalProperties: false
    properties:
      albums:
        type: object
        additionalProperties:
          type: object
          additionalProperties: false
          properties:
            title: { type: string }
            jacket:
              type: string
              x-ref:
                entity: blob
          required: [title, jacket]
"""


def test_blob_file_becomes_record_and_is_fk_target(tmp_path: Path) -> None:
    """End-to-end: a non-YAML/Markdown file becomes a blob record that the
    catalog registers, so an ``x-ref`` to ``blob`` resolves against it.

    ``covers/day1.png`` present ⇒ ``a1.jacket`` resolves; ``covers/missing.png``
    absent ⇒ ``a2.jacket`` dangles and is reported.
    """
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(dedent(_BLOB_FK_SCHEMA).lstrip("\n"))
    src = tmp_path / "contents"
    (src / "covers").mkdir(parents=True)
    (src / "covers" / "day1.png").write_bytes(b"\x89PNG\r\n")
    (src / "data.yaml").write_text(
        dedent("""
            albums:
              a1:
                title: Day 1
                jacket: covers/day1.png
              a2:
                title: Day 2
                jacket: covers/missing.png
        """).lstrip("\n")
    )
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    inspect_schema.fn(schema_file, out_dir=catalog_dir)
    out = tmp_path / "normalized"
    out.mkdir()

    reporter = DiagnosticReporter()
    normalize_contents.fn(
        src_dir=src,
        out_dir=out,
        schema_file=schema_file,
        data_catalog_dir=catalog_dir,
        reporter=reporter,
    )

    # Only the absent target dangles; the present blob resolves.
    assert [(d.source, d.message) for d in reporter.diagnostics] == [
        (
            "x-ref-data",
            "x-ref albums.jacket = 'covers/missing.png' has no match in blob.id",
        ),
    ]
    # The blob's metadata record lands on disk (its bytes do not — that is H5).
    assert yaml.safe_load((out / "covers" / "day1.png.yaml").read_text()) == {
        "blob": [{"id": "covers/day1.png", "mime_type": "image/png"}]
    }
