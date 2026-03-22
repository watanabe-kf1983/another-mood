"""Tests for Generator — views YAML loading and Jinja2 rendering."""

from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from reqs_builder.generator import generate, load_views


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestLoadViews:
    def test_single_file(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(
            views_dir / "entities.yaml",
            {"entities": [{"id": "user", "name": "User"}]},
        )

        assert load_views(views_dir) == {
            "entities": [{"id": "user", "name": "User"}],
        }

    def test_merges_multiple_files(self, tmp_path: Path) -> None:
        """Distinct top-level keys from separate files are merged."""
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        _write_yaml(views_dir / "entities.yaml", {"entities": [{"id": "user"}]})
        _write_yaml(
            views_dir / "relations.yaml",
            {"relations": [{"from": "user", "to": "role"}]},
        )

        result = load_views(views_dir)
        assert list(result.keys()) == ["entities", "relations"]

    def test_empty_dir_returns_empty_dict(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()

        assert load_views(views_dir) == {}

    def test_non_yaml_files_ignored(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "readme.md").write_text("# Not YAML")
        _write_yaml(views_dir / "data.yaml", {"key": "value"})

        assert load_views(views_dir) == {"key": "value"}


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
