"""Tests for generate — orchestration of rendering and error handling."""

from pathlib import Path
from typing import Any

import yaml

from reqs_builder.components.generator.generator import generate


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestGenerate:
    def test_renders_normal_output(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        assert (out_dir / "data" / "index.md").read_text() == "# Hello\n"
        # __meta_root is always rendered alongside __root.
        assert (out_dir / "data" / "__reference" / "index.md").exists()

    def test_renders_error_page_on_template_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text('{% section "bad" with x %}')

        out_dir = tmp_path / "output"
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        error_page = (out_dir / "data" / "index.md").read_text()
        assert error_page.startswith("# Build Report")

    def test_replaces_stale_output_with_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"

        # First build succeeds
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )
        assert (out_dir / "data" / "index.md").read_text() == "# Hello\n"

        # Break the template
        (templates_dir / "index.md").write_text('{% section "bad" with title %}')
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        # Stale output is gone, error page is shown
        data_out = out_dir / "data"
        error_page = (data_out / "index.md").read_text()
        assert "# Build Report" in error_page
        assert sorted(p.name for p in data_out.iterdir()) == [
            "index.md",
        ]
