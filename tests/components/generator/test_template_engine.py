"""Tests for TemplateEngine."""

from pathlib import Path

import pytest
from markupsafe import Markup

from another_mood.components.generator.template_engine import (
    OutputFormat,
    TemplateEngine,
    make_environment,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


class TestRender:
    def test_renders_template(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.md").write_text("# {{ title }}\n")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})
        result = engine.render("hello.md", {"title": "World"})
        assert result == "# World\n"


class TestThisBinding:
    """The render boundary binds the subject as ``this`` uniformly — the
    root template and mood_view subtemplates see data the same way."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        return TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})

    def test_mapping_subject_is_spread_and_bound_as_this(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ name }}/{{ this.name }}")
        assert engine.render("t.md", {"name": "Alice"}) == "Alice/Alice"

    def test_non_mapping_subject_is_iterated_via_this(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{% for x in this %}{{ x }}{% endfor %}")
        assert engine.render("t.md", ["a", "b", "c"]) == "abc"

    def test_subject_key_named_this_is_shadowed_by_the_node(
        self, tmp_path: Path
    ) -> None:
        # ``this`` is reserved: a subject field of that name loses to the
        # node binding (here the string "ignored" is dropped, so
        # ``this.name`` resolves on the node, not on "ignored").
        engine = self._engine(tmp_path, "{{ this.name }}/{{ name }}")
        subject = {"name": "Bob", "this": "ignored"}
        assert engine.render("t.md", subject) == "Bob/Bob"


class TestFiltersParam:
    """TemplateEngine forwards a `filters` mapping to the Jinja2 environment."""

    def test_registers_custom_filter(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ 'hi' | shout }}")

        def shout(value: object) -> str:
            return str(value).upper()

        engine = TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            filters={"shout": shout},
        )
        assert engine.render("t.md", {}) == "HI"


class TestMakeEnvironment:
    """`make_environment` wires an OutputFormat's escape into Jinja2's
    finalize hook and registers the format's globals and filters."""

    def test_applies_escape_to_bare_strings(self) -> None:
        fmt = OutputFormat(
            name="upper",
            escape=lambda s: s.upper(),
        )
        env = make_environment(fmt)
        template = env.from_string("{{ value }}")
        assert template.render(value="hello") == "HELLO"

    def test_passes_markup_through_without_escape(self) -> None:
        fmt = OutputFormat(
            name="upper",
            escape=lambda s: s.upper(),
        )
        env = make_environment(fmt)
        template = env.from_string("{{ value }}")
        assert template.render(value=Markup("hello")) == "hello"

    def test_renders_none_as_empty_string(self) -> None:
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        template = env.from_string("[{{ value }}]")
        assert template.render(value=None) == "[]"

    def test_renders_undefined_as_empty_string(self) -> None:
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        template = env.from_string("[{{ missing }}]")
        assert template.render() == "[]"

    def test_registers_format_filters(self) -> None:
        def shout(v: object) -> str:
            return str(v).upper() + "!"

        fmt = OutputFormat(name="shout", escape=lambda s: s, filters={"shout": shout})
        env = make_environment(fmt)
        template = env.from_string("{{ 'hi' | shout }}")
        assert template.render() == "HI!"

    def test_registers_format_globals(self) -> None:
        def greet(name: object) -> str:
            return f"hello {name}"

        fmt = OutputFormat(name="g", escape=lambda s: s, globals={"greet": greet})
        env = make_environment(fmt)
        template = env.from_string("{{ greet('world') }}")
        assert template.render() == "hello world"

    def test_filter_returning_markup_bypasses_finalize_escape(self) -> None:
        def raw(v: object) -> Markup:
            return Markup(str(v))

        fmt = OutputFormat(
            name="upper",
            escape=lambda s: s.upper(),
            filters={"raw": raw},
        )
        env = make_environment(fmt)
        template = env.from_string("{{ 'hi' | raw }}")
        assert template.render() == "hi"


class TestTemplateEngineMdEscape:
    """End-to-end: TemplateEngine wires the `md` OutputFormat by default."""

    def test_escapes_bare_string_substitution(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value }}")
        engine = TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})
        assert engine.render("t.md", {"value": "a|b"}) == "a\\|b"

    def test_safe_filter_bypasses_escape(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value | safe }}")
        engine = TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})
        assert engine.render("t.md", {"value": "# heading"}) == "# heading"

    def test_md_helpers_are_auto_available(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(
            "{{ code_inline('x') }}|{{ 'a|b' | in_cell }}|{{ 'a b' | as_url }}"
        )
        engine = TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})
        assert engine.render("t.md", {}) == "`x`|a\\|b|a%20b"


class TestTemplateSyntaxErrorConversion:
    def test_raises_file_validation_error(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.md").write_text("{% mood_view bad %}")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir, filters={})
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("bad.md", {})

        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].source == "jinja2"
        assert diags[0].line is not None
        assert "bad.md" in str(diags[0].file)
