"""Tests for Normalizer."""

from pathlib import Path

import yaml

from reqs_builder.components.normalizer import normalize, normalize_markdown


class TestNormalize:
    """normalize dispatches md vs non-md correctly."""

    def test_dispatches_md_and_yaml(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("key: value\n")
        (src / "notes.md").write_text("# Notes\n")

        out = tmp_path / "normalized"
        normalize(src, out)

        # YAML copied as-is
        assert (out / "data.yaml").read_text() == "key: value\n"
        # Markdown converted to .yaml, not copied
        assert (out / "notes.yaml").exists()
        assert not (out / "notes.md").exists()


class TestNormalizeMarkdown:
    def test_writes_prose_yaml(self, tmp_path: Path) -> None:
        src = tmp_path / "guide.md"
        src.write_text("# Guide\n\nSteps.\n")
        out_dir = tmp_path / "out"

        normalize_markdown(src, Path("guide.md"), out_dir)

        data = yaml.safe_load((out_dir / "guide.yaml").read_text())
        assert data["prose"][0]["id"] == "guide"
        assert data["prose"][0]["title"] == "Guide"
        assert data["prose"][0]["body"]["_mime_type"] == "text/markdown"

    def test_subdirectory_id(self, tmp_path: Path) -> None:
        src = tmp_path / "sub" / "doc.md"
        src.parent.mkdir()
        src.write_text("# Doc\n")
        out_dir = tmp_path / "out"

        normalize_markdown(src, Path("sub/doc.md"), out_dir)

        data = yaml.safe_load((out_dir / "sub" / "doc.yaml").read_text())
        assert data["prose"][0]["id"] == "sub/doc"
