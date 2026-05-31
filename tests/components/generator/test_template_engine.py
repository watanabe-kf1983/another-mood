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


class TestSourceStack:
    """current_source() is the out_dir-relative path of the page currently
    being rendered. render_to_file pushes (and pops on exit); render
    inherits the stack so inline {% mood_view %} fragments see the
    enclosing page's source."""

    def test_push_inherit_pop_through_nested_and_inline(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        # Variable inputs to the filter (`data.id`, `k`, `id`) keep Jinja2's
        # optimizer from constant-folding the filter call at compile time.
        (templates_dir / "outer.md").write_text(
            "{{ data.id | record }}|"
            '{% mood_view "inline.md" with data inline %}|'
            "{{ data.id | record }}|"
            '{% mood_view "inner.md" with data %}'
            "{{ data.id | record }}"
        )
        (templates_dir / "inline.md").write_text("{{ id | record }}")
        (templates_dir / "inner.md").write_text("{{ id | record }}")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        captured: list[Path | None] = []
        # Late binding: filter closes over `engine` by name; the closure
        # resolves it at call time, after TemplateEngine has been built.
        engine: TemplateEngine | None = None

        def record(value: object) -> object:
            assert engine is not None
            captured.append(engine.current_source())
            return value

        engine = TemplateEngine(
            out_dir, templates_dir=templates_dir, filters={"record": record}
        )
        assert engine.current_source() is None  # empty initially

        engine.render_to_file("outer.md", {"data": {"id": "x"}}, Path("outer.md"))

        assert captured == [
            Path("outer.md"),  # outer, before inline
            Path("outer.md"),  # inline inherits outer
            Path("outer.md"),  # outer, after inline
            Path("inner/x.md"),  # inner pushes its own
            Path("outer.md"),  # outer, after inner pops
        ]
        assert engine.current_source() is None  # popped on exit

    def test_stack_pops_and_no_partial_write_on_render_failure(
        self, tmp_path: Path
    ) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.md").write_text("{% mood_view bad %}")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        engine = TemplateEngine(out_dir, templates_dir=templates_dir, filters={})
        with pytest.raises(FileValidationError):
            engine.render_to_file("bad.md", {}, Path("bad.md"))

        assert engine.current_source() is None
        assert not (out_dir / "bad.md").exists()
