"""Tests for Normalizer."""

from pathlib import Path

import pytest
import yaml

from reqs_builder.components.preprocess.normalizer import (
    build_contents_validator,
    check,
    normalize_contents,
)
from reqs_builder.components.shared.diagnostic import FileValidationError


class TestNormalizeContents:
    """normalize_contents: parse → validate → write for all file types."""

    @pytest.fixture()
    def schema_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "schema"
        d.mkdir()
        return d

    def test_dispatches_md_and_yaml(self, tmp_path: Path, schema_dir: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("key: value\n")
        (src / "notes.md").write_text("# Notes\n")

        out = tmp_path / "normalized"
        normalize_contents(src_dir=src, out_dir=out, schema_dir=schema_dir)

        # YAML written as .yaml
        data = yaml.safe_load((out / "data.yaml").read_text())
        assert data == {"key": "value"}
        # Markdown converted to .yaml, not copied
        assert (out / "notes.yaml").exists()
        assert not (out / "notes.md").exists()

    def test_markdown_prose_output(self, tmp_path: Path, schema_dir: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "guide.md").write_text("# Guide\n\nSteps.\n")

        out = tmp_path / "normalized"
        normalize_contents(src_dir=src, out_dir=out, schema_dir=schema_dir)

        data = yaml.safe_load((out / "guide.yaml").read_text())
        assert data["prose"][0]["id"] == "guide"
        assert data["prose"][0]["title"] == "Guide"
        assert data["prose"][0]["body"]["mime_type"] == "text/markdown"

    def test_markdown_subdirectory_id(self, tmp_path: Path, schema_dir: Path) -> None:
        src = tmp_path / "contents"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "doc.md").write_text("# Doc\n")

        out = tmp_path / "normalized"
        normalize_contents(src_dir=src, out_dir=out, schema_dir=schema_dir)

        data = yaml.safe_load((out / "sub" / "doc.yaml").read_text())
        assert data["prose"][0]["id"] == "sub/doc"


# ── check ─────────────────────────────────────────────────────────


class TestCheck:
    """check: parse + validate all files in src_dir."""

    @pytest.fixture()
    def schema_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "schema"
        d.mkdir()
        (d / "entities.yaml").write_text(
            "schemas:\n"
            "  entities:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        id: { type: string }\n"
            "        name: { type: string }\n"
            "      required: [id, name]\n"
        )
        return d

    def test_valid_content_passes(self, tmp_path: Path, schema_dir: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text("entities:\n  - id: user\n    name: User\n")
        check(src, build_contents_validator(schema_dir))

    def test_invalid_content_raises(self, tmp_path: Path, schema_dir: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text(
            "entities:\n"
            "  - id: 123\n"  # type error: integer instead of string
            "    name: User\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            check(src, build_contents_validator(schema_dir))
        assert len(exc_info.value.diagnostics) >= 1
        assert exc_info.value.diagnostics[0].source == "jsonschema"

    def test_markdown_validated_against_prose_schema(
        self, tmp_path: Path, schema_dir: Path
    ) -> None:
        """Markdown produces {prose: [...]}, validated against built-in prose schema."""
        src = tmp_path / "contents"
        src.mkdir()
        (src / "notes.md").write_text("# Notes\n")
        check(src, build_contents_validator(schema_dir))

    def test_unschematized_yaml_passes(self, tmp_path: Path, schema_dir: Path) -> None:
        """YAML files with keys not in schemas pass (additionalProperties allowed)."""
        src = tmp_path / "contents"
        src.mkdir()
        (src / "config.yaml").write_text("config:\n  debug: true\n")
        check(src, build_contents_validator(schema_dir))

    def test_collects_errors_across_files(
        self, tmp_path: Path, schema_dir: Path
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text("entities:\n  - id: 123\n    name: ok\n")
        (schema_dir / "relations.yaml").write_text(
            "schemas:\n"
            "  relations:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      required: [from, to]\n"
        )
        (src / "relations.yaml").write_text(
            "relations:\n  - description: missing required\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            check(src, build_contents_validator(schema_dir))
        files = {str(d.file) for d in exc_info.value.diagnostics}
        assert len(files) == 2


# ── build_contents_validator ───────────────────────────────────────


class TestBuildContentsValidator:
    """build_contents_validator: merge built-in prose + user schemas."""

    def test_merges_builtin_and_user_schemas(self, tmp_path: Path) -> None:
        schema_dir = tmp_path / "schema"
        schema_dir.mkdir()
        (schema_dir / "entities.yaml").write_text(
            "schemas:\n"
            "  entities:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        id: { type: string }\n"
            "      required: [id]\n"
        )
        validator = build_contents_validator(schema_dir)

        # User schema: entities validated
        errors = validator.validate({"entities": [{"id": 123}]}, Path("test.yaml"))
        assert len(errors) >= 1

        # Built-in prose schema: prose validated
        errors = validator.validate(
            {
                "prose": [
                    {
                        "id": "doc",
                        "body": {"mime_type": "text/markdown", "content": "x"},
                    }
                ]
            },
            Path("test.yaml"),
        )
        assert errors == []

    def test_nonexistent_schema_dir_uses_builtin_only(self) -> None:
        validator = build_contents_validator(Path("/nonexistent"))

        # prose still validated
        errors = validator.validate(
            {
                "prose": [
                    {
                        "id": "doc",
                        "body": {"mime_type": "text/markdown", "content": "x"},
                    }
                ]
            },
            Path("test.yaml"),
        )
        assert errors == []
