"""Tests for render — template rendering and writing."""

from pathlib import Path
from textwrap import dedent

from reqs_builder.components.generator.generator import render


class TestWriteIndex:
    def test_renders_user_template(self, tmp_path: Path) -> None:
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
        data = {"items": [{"name": "Alice"}, {"name": "Bob"}]}
        render("__root", data, out_dir, templates_dir=templates_dir)

        assert (out_dir / "index.md").read_text() == dedent("""\
            # List

            - Alice
            - Bob

        """)

    def test_renders_error_template(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        data = {
            "__errors": [
                {
                    "source": "contents/entities.yaml",
                    "message": "Unknown field 'stauts'",
                    "traceback": "Traceback ...\nValidationError: Unknown field",
                }
            ]
        }
        render("__errors", data, out_dir)

        result = (out_dir / "index.md").read_text()
        assert "# Build Error" in result
        assert "contents/entities.yaml" in result
        assert "Unknown field 'stauts'" in result
        assert "Traceback" in result
