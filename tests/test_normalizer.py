"""Tests for Normalizer — passthrough copy of contents."""

from pathlib import Path
from typing import Any

import yaml


from reqs_builder.normalizer import normalize


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestNormalize:
    def test_copies_yaml_files(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        _write_yaml(src / "entities.yaml", {"entities": [{"id": "user"}]})
        _write_yaml(src / "relations.yaml", {"relations": [{"from": "a", "to": "b"}]})

        out = tmp_path / "normalized"
        normalize(src, out)

        assert yaml.safe_load((out / "entities.yaml").read_text()) == {
            "entities": [{"id": "user"}],
        }
        assert yaml.safe_load((out / "relations.yaml").read_text()) == {
            "relations": [{"from": "a", "to": "b"}],
        }

    def test_markdown_files_become_yaml(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "guide.md").write_text("# Guide\n\nSteps.\n")

        out = tmp_path / "normalized"
        normalize(src, out)

        guide = yaml.safe_load((out / "sub" / "guide.yaml").read_text())
        assert guide["prose"][0]["id"] == "sub/guide"
        assert not (out / "sub" / "guide.md").exists()

    def test_copies_subdirectories(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        (src / "sub").mkdir(parents=True)
        _write_yaml(src / "sub" / "data.yaml", {"key": "value"})

        out = tmp_path / "normalized"
        normalize(src, out)

        assert yaml.safe_load((out / "sub" / "data.yaml").read_text()) == {
            "key": "value",
        }

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "contents"
        src.mkdir()
        _write_yaml(src / "data.yaml", {"x": 1})

        out = tmp_path / "deep" / "nested" / "normalized"
        normalize(src, out)

        assert (out / "data.yaml").exists()
