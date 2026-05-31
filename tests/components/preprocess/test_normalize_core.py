"""Tests for normalize core (check, iter_normalized, write_file)."""

from pathlib import Path

import pytest
import yaml

from another_mood.components.preprocess.content_normalizer import build_contents_schema
from another_mood.components.preprocess.normalize_core import check, iter_normalized
from another_mood.components.shared.user_source.diagnostic import FileValidationError
from another_mood.components.shared.json_data_model import save_model


def _normalize(src: Path, out: Path, schema: dict[str, object]) -> None:
    """Inline the same pipeline both callers use, for test brevity."""
    for src_file, data in iter_normalized(src, schema):
        rel = src_file.relative_to(src)
        save_model(out / rel.with_name(rel.name + ".yaml"), data)


class TestIterNormalizedAndWrite:
    """iter_normalized + write_file: parse → normalize → write for all file types."""

    @pytest.fixture()
    def schema(self, tmp_path: Path) -> dict[str, object]:
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
        return dict(build_contents_schema(schema_file))

    def test_dispatches_md_and_yaml(
        self, tmp_path: Path, schema: dict[str, object]
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("items:\n  - name: a\n")
        (src / "notes.md").write_text("# Notes\n")

        out = tmp_path / "normalized"
        _normalize(src, out, schema)

        # Output name is source name + ".yaml" (appended, not replaced)
        data = yaml.safe_load((out / "data.yaml.yaml").read_text())
        assert data == {"items": [{"name": "a"}]}
        # Markdown converted to YAML at .md.yaml, not copied
        assert (out / "notes.md.yaml").exists()
        assert not (out / "notes.md").exists()

    def test_markdown_prose_output(
        self, tmp_path: Path, schema: dict[str, object]
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "guide.md").write_text("# Guide\n\nSteps.\n")

        out = tmp_path / "normalized"
        _normalize(src, out, schema)

        data = yaml.safe_load((out / "guide.md.yaml").read_text())
        assert data["prose"][0]["id"] == "guide"
        assert data["prose"][0]["title"] == "Guide"
        assert data["prose"][0]["body"]["mime_type"] == "text/markdown"

    def test_markdown_subdirectory_id(
        self, tmp_path: Path, schema: dict[str, object]
    ) -> None:
        src = tmp_path / "contents"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "doc.md").write_text("# Doc\n")

        out = tmp_path / "normalized"
        _normalize(src, out, schema)

        data = yaml.safe_load((out / "sub" / "doc.md.yaml").read_text())
        assert data["prose"][0]["id"] == "sub/doc"

    def test_same_stem_different_extensions_do_not_collide(
        self, tmp_path: Path, schema: dict[str, object]
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "items.yaml").write_text("items:\n  - name: a\n")
        (src / "items.yml").write_text("items:\n  - name: b\n")
        (src / "items.md").write_text("# Items\n")

        out = tmp_path / "normalized"
        _normalize(src, out, schema)

        # Each source produces a distinct destination — nothing is overwritten.
        assert (out / "items.yaml.yaml").exists()
        assert (out / "items.yml.yaml").exists()
        assert (out / "items.md.yaml").exists()

    def test_unrecognized_extensions_are_ignored(
        self, tmp_path: Path, schema: dict[str, object]
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("items:\n  - name: a\n")
        # Files with unsupported extensions must not be treated as YAML.
        (src / "notes.txt").write_text("not valid yaml: { [")
        (src / "README").write_text("project readme")

        out = tmp_path / "normalized"
        _normalize(src, out, schema)

        assert (out / "data.yaml.yaml").exists()
        assert not (out / "notes.txt.yaml").exists()
        assert not (out / "README.yaml").exists()


class TestCheck:
    """check: parse + validate all files in src_dir."""

    @pytest.fixture()
    def schema_file(self, tmp_path: Path) -> Path:
        f = tmp_path / "schema.yaml"
        f.write_text(
            "type: object\n"
            "properties:\n"
            "  entities:\n"
            "    type: array\n"
            "    items:\n"
            "      type: object\n"
            "      properties:\n"
            "        id: { type: string }\n"
            "        name: { type: string }\n"
            "      required: [id, name]\n"
            "additionalProperties: false\n"
        )
        return f

    def test_valid_content_passes(self, tmp_path: Path, schema_file: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text("entities:\n  - id: user\n    name: User\n")
        check(src, build_contents_schema(schema_file))

    def test_invalid_content_raises(self, tmp_path: Path, schema_file: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text(
            "entities:\n"
            "  - id: 123\n"  # type error: integer instead of string
            "    name: User\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            check(src, build_contents_schema(schema_file))
        assert len(exc_info.value.diagnostics) >= 1
        assert exc_info.value.diagnostics[0].source == "jsonschema"

    def test_markdown_validated_against_prose_schema(
        self, tmp_path: Path, schema_file: Path
    ) -> None:
        """Markdown produces {prose: [...]}, validated against built-in prose schema."""
        src = tmp_path / "contents"
        src.mkdir()
        (src / "notes.md").write_text("# Notes\n")
        check(src, build_contents_schema(schema_file))

    def test_unschematized_yaml_rejected(
        self, tmp_path: Path, schema_file: Path
    ) -> None:
        """YAML files with keys not in any schema are rejected."""
        src = tmp_path / "contents"
        src.mkdir()
        (src / "config.yaml").write_text("config:\n  debug: true\n")
        with pytest.raises(FileValidationError):
            check(src, build_contents_schema(schema_file))

    def test_collects_errors_across_files(
        self, tmp_path: Path, schema_file: Path
    ) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "entities.yaml").write_text("entities:\n  - id: 123\n    name: ok\n")
        (src / "more.yaml").write_text("entities:\n  - id: ok\n  # missing name\n")
        with pytest.raises(FileValidationError) as exc_info:
            check(src, build_contents_schema(schema_file))
        files = {str(d.file) for d in exc_info.value.diagnostics}
        assert len(files) == 2
