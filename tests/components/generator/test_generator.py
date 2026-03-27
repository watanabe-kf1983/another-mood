"""Tests for Generator — Jinja2 rendering."""

from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from reqs_builder.components.generator.generator import generate


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestGenerate:
    def test_renders_index_with_data(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_yaml(
            data_dir / "data.yaml",
            {"items": [{"name": "Alice"}, {"name": "Bob"}]},
        )

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text(
            dedent("""\
            # List

            {% for item in items -%}
            - {{ item.name }}
            {% endfor %}
        """)
        )

        out_dir = tmp_path / "output"
        generate(data_dir, templates_dir, out_dir)

        assert (out_dir / "index.md").read_text() == dedent("""\
            # List

            - Alice
            - Bob

        """)


class TestGenerateErrorTemplate:
    def test_renders_errors_from_data(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_yaml(
            data_dir / "errors.yaml",
            {
                "__errors": [
                    {
                        "source": "contents/entities.yaml",
                        "message": "Unknown field 'stauts'",
                        "traceback": "Traceback ...\nValidationError: Unknown field",
                    }
                ]
            },
        )

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# Normal\n")

        out_dir = tmp_path / "output"
        generate(data_dir, templates_dir, out_dir)

        result = (out_dir / "index.md").read_text()
        assert "# Build Error" in result
        assert "contents/entities.yaml" in result
        assert "Unknown field 'stauts'" in result
        assert "Traceback" in result

    def test_renders_normal_when_no_errors(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"
        generate(data_dir, templates_dir, out_dir)

        assert (out_dir / "index.md").read_text() == "# Hello\n"


class TestGenerateErrorPage:
    def test_writes_error_page_on_template_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_yaml(data_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text('{% section "bad" with x %}')

        out_dir = tmp_path / "output"
        generate(data_dir, templates_dir, out_dir)

        error_page = (out_dir / "index.md").read_text()
        assert error_page.startswith("# Build Error")

    def test_replaces_stale_output_with_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"

        # First build succeeds
        generate(data_dir, templates_dir, out_dir)
        assert (out_dir / "index.md").read_text() == "# Hello\n"

        # Break the template
        (templates_dir / "index.md").write_text('{% section "bad" with title %}')
        generate(data_dir, templates_dir, out_dir)

        # Stale output is gone, error page is shown
        error_page = (out_dir / "index.md").read_text()
        assert "# Build Error" in error_page
        assert len(list(out_dir.iterdir())) == 1
