"""Tests for TemplateEngine."""

from pathlib import Path

import pytest

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.diagnostic import FileValidationError


class TestRender:
    def test_renders_template(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.md").write_text("# {{ title }}\n")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
        result = engine.render("hello", {"title": "World"})
        assert result == "# World\n"


class TestTemplateSyntaxErrorConversion:
    def test_raises_file_validation_error(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.md").write_text("{% section bad %}")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("bad", {})

        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].source == "jinja2"
        assert diags[0].line is not None
        assert "bad.md" in str(diags[0].file)
