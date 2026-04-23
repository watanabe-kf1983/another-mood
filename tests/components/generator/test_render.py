"""Tests for render — template rendering and writing."""

from pathlib import Path
from textwrap import dedent

from another_mood.components.generator.generator import render


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
        render("__reports", data, out_dir, templates_dir=templates_dir)

        assert (out_dir / "index.md").read_text() == dedent("""\
            # List

            - Alice
            - Bob

        """)

    def test_renders_build_report_with_diagnostics(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        data = {
            "errors": [
                {"message": "FileValidationError: 1 validation error"},
            ],
            "diagnostics": [
                {
                    "file": "contents/entities.yaml",
                    "line": 10,
                    "column": 3,
                    "message": "Unknown field 'stauts'",
                    "severity": "error",
                    "source": "normalizer",
                }
            ],
        }
        render("__build_report", data, out_dir)

        result = (out_dir / "index.md").read_text()
        assert "# Build Report" in result
        assert "contents/entities.yaml" in result
        assert "Unknown field 'stauts'" in result

    def test_renders_build_report_with_snippet(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        data = {
            "diagnostics": [
                {
                    "file": "x.yaml",
                    "line": 1,
                    "column": 1,
                    "message": "bad",
                    "snippet": "> 1 | bad value\n    | ^",
                }
            ],
        }
        render("__build_report", data, out_dir)

        result = (out_dir / "index.md").read_text()
        assert "```\n> 1 | bad value\n    | ^\n```" in result

    def test_renders_build_report_with_traceback(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        data = {
            "errors": [
                {
                    "message": "KeyError: 'schemas'",
                    "traceback": "Traceback ...\nKeyError: 'schemas'",
                }
            ],
        }
        render("__build_report", data, out_dir)

        result = (out_dir / "index.md").read_text()
        assert "# Build Report" in result
        assert "KeyError" in result
        assert "Traceback" in result
