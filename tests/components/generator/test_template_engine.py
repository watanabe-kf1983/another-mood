"""Tests for TemplateEngine."""

from pathlib import Path

import pytest
from markupsafe import Markup

from another_mood.components.generator.template_engine import (
    MD,
    OutputFormat,
    TemplateEngine,
    make_environment,
    md_escape,
)
from another_mood.components.shared.diagnostic import FileValidationError


class TestRender:
    def test_renders_template(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.md").write_text("# {{ title }}\n")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
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
    finalize hook and registers the format's filters."""

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


class TestMdEscape:
    """`md_escape` backslash-escapes every ASCII punctuation character.

    CommonMark spec: any ASCII punctuation may be backslash-escaped; the
    rendered output matches the unescaped character. Blanket-escaping is
    therefore safe and avoids accidental syntax.
    """

    def test_leaves_whitespace_unescaped(self) -> None:
        # Space (0x20) is below the punctuation range; only punct is touched.
        assert md_escape("# hi") == "\\# hi"

    def test_escapes_each_ascii_punctuation(self) -> None:
        punctuation = (
            "!\"#$%&'()*+,-./"  # 0x21–0x2F
            ":;<=>?@"  # 0x3A–0x40
            "[\\]^_`"  # 0x5B–0x60
            "{|}~"  # 0x7B–0x7E
        )
        escaped = md_escape(punctuation)
        # Every character should be preceded by a backslash.
        assert escaped == "".join("\\" + c for c in punctuation)

    def test_leaves_alphanumerics_untouched(self) -> None:
        assert md_escape("abc XYZ 123") == "abc XYZ 123"

    def test_leaves_non_ascii_untouched(self) -> None:
        # Non-ASCII punctuation (Japanese, em-dash, etc.) is outside the
        # CommonMark backslash-escape spec and must pass through unchanged.
        assert md_escape("見出し — テスト") == "見出し — テスト"

    def test_escapes_backslash_itself(self) -> None:
        # The escape character must itself be escaped so existing backslashes
        # in user data round-trip correctly.
        assert md_escape("\\") == "\\\\"

    def test_empty_string(self) -> None:
        assert md_escape("") == ""


class TestMdOutputFormat:
    """`MD` is the canonical Markdown output format used by TemplateEngine."""

    def test_name_is_md(self) -> None:
        assert MD.name == "md"

    def test_escape_applies_md_escape(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value }}")
        # `|` inside a table cell would split the column without escape.
        assert template.render(value="a|b") == "a\\|b"

    def test_markup_bypasses_md_escape(self) -> None:
        env = make_environment(MD)
        template = env.from_string("{{ value | safe }}")
        # Code-fence / code-span / Markup-marked content must pass through
        # untouched — md_escape's `\` would be literal in those contexts.
        assert template.render(value="# heading") == "# heading"


class TestTemplateEngineMdEscape:
    """End-to-end: TemplateEngine wires the `md` OutputFormat by default."""

    def test_escapes_bare_string_substitution(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value }}")
        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
        assert engine.render("t.md", {"value": "a|b"}) == "a\\|b"

    def test_safe_filter_bypasses_escape(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value | safe }}")
        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
        assert engine.render("t.md", {"value": "# heading"}) == "# heading"


class TestTemplateSyntaxErrorConversion:
    def test_raises_file_validation_error(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.md").write_text("{% mood_view bad %}")

        engine = TemplateEngine(tmp_path, templates_dir=templates_dir)
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("bad.md", {})

        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].source == "jinja2"
        assert diags[0].line is not None
        assert "bad.md" in str(diags[0].file)
