"""Tests for Normalizer."""

from pathlib import Path

import yaml

from reqs_builder.components.preprocess.normalizer import normalize


class TestNormalize:
    """normalize: parse → validate → write for all file types."""

    def test_dispatches_md_and_yaml(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "data.yaml").write_text("key: value\n")
        (src / "notes.md").write_text("# Notes\n")

        out = tmp_path / "normalized"
        normalize(src_dir=src, out_dir=out)

        # YAML written as .yaml
        data = yaml.safe_load((out / "data.yaml").read_text())
        assert data == {"key": "value"}
        # Markdown converted to .yaml, not copied
        assert (out / "notes.yaml").exists()
        assert not (out / "notes.md").exists()

    def test_markdown_prose_output(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        (src / "guide.md").write_text("# Guide\n\nSteps.\n")

        out = tmp_path / "normalized"
        normalize(src_dir=src, out_dir=out)

        data = yaml.safe_load((out / "guide.yaml").read_text())
        assert data["prose"][0]["id"] == "guide"
        assert data["prose"][0]["title"] == "Guide"
        assert data["prose"][0]["body"]["mime_type"] == "text/markdown"

    def test_markdown_subdirectory_id(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "doc.md").write_text("# Doc\n")

        out = tmp_path / "normalized"
        normalize(src_dir=src, out_dir=out)

        data = yaml.safe_load((out / "sub" / "doc.yaml").read_text())
        assert data["prose"][0]["id"] == "sub/doc"
