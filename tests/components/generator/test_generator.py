"""Tests for Generator — Jinja2 rendering."""

from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from reqs_builder.components.generator.core import generate


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestGenerate:
    def test_renders_index_with_views_data(self, tmp_path: Path) -> None:
        """Views keys are accessible as template variables."""
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(
            views_dir / "data.yaml",
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
        generate(views_dir, templates_dir, out_dir)

        assert (out_dir / "index.md").read_text() == dedent("""\
            # List

            - Alice
            - Bob

        """)

    def test_merges_multiple_yaml_for_template(self, tmp_path: Path) -> None:
        """Data from multiple YAML files is available in the same template."""
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(views_dir / "entities.yaml", {"entities": [{"name": "User"}]})
        _write_yaml(
            views_dir / "relations.yaml",
            {"relations": [{"from": "user", "to": "role"}]},
        )

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text(
            dedent("""\
            {% for e in entities -%}
            {{ e.name }}
            {% endfor -%}
            {% for r in relations -%}
            {{ r.from }}>{{ r.to }}
            {% endfor %}
        """)
        )

        out_dir = tmp_path / "output"
        generate(views_dir, templates_dir, out_dir)

        assert (out_dir / "index.md").read_text() == dedent("""\
            User
            user>role

        """)

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        """Output directory is created if it doesn't exist."""
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(views_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "deeply" / "nested" / "output"
        generate(views_dir, templates_dir, out_dir)

        assert (out_dir / "index.md").read_text() == "# Hello\n"


class TestGenerateErrorPage:
    def test_writes_error_page_on_template_error(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(views_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text('{% section "bad" with x %}')

        out_dir = tmp_path / "output"
        generate(views_dir, templates_dir, out_dir)

        error_page = (out_dir / "index.md").read_text()
        assert error_page.startswith("# Build Error")

    def test_replaces_stale_output_with_error(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(views_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"

        # First build succeeds
        generate(views_dir, templates_dir, out_dir)
        assert (out_dir / "index.md").read_text() == "# Hello\n"

        # Break the template
        (templates_dir / "index.md").write_text('{% section "bad" with title %}')
        generate(views_dir, templates_dir, out_dir)

        # Stale output is gone, error page is shown
        error_page = (out_dir / "index.md").read_text()
        assert "# Build Error" in error_page
        assert len(list(out_dir.iterdir())) == 1
