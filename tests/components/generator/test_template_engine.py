"""Tests for TemplateEngine."""

from pathlib import Path

import pytest
from markupsafe import Markup
from minijinja import TemplateError

from another_mood.components.generator.data_tree_filters import MissingNode
from another_mood.components.generator.output_formats.md import MD
from another_mood.components.generator.template_engine import (
    EnvironmentPool,
    OutputFormat,
    PageCollisionError,
    PathRegistry,
    TemplateEngine,
    make_environment,
    as_template_helper,
)
from another_mood.components.shared.user_error import UserError
from another_mood.components.shared.user_source.diagnostic import FileValidationError


class TestRender:
    def test_renders_template(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.md").write_text("# {{ title }}\n")

        engine = TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )
        result = engine.render("hello.md", {"title": "World"})
        assert result == "# World\n"


class TestThisBinding:
    """The render boundary binds the subject as ``this`` uniformly — the
    root template and render subtemplates see data the same way."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        return TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )

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


class TestRenderBoundaryAcceptsTemplateSafe:
    """A render subject comes from a template expression, so it is
    ``TemplateSafe`` — wider than the inert data model."""

    def _engine(
        self, tmp_path: Path, body: str, output_format: OutputFormat = MD
    ) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text(body)
        (templates_dir / "sub.md").write_text("[{{ this }}]")
        return TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            output_format=output_format,
            filters={},
        )

    def test_undefined_subject_renders_as_empty(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, '{{ mispelled | render("sub.md") }}')
        assert engine.render("t.md", {"spelled": "x"}) == "[]"

    def test_missing_node_subject_is_rendered(self, tmp_path: Path) -> None:
        # `upper` keeps the assertion off md's punctuation escaping.
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        engine = self._engine(tmp_path, '{{ this | render("sub.md") }}', fmt)
        subject = MissingNode(anchor_path="/unresolved/ref")
        assert engine.render("t.md", subject) == "[/UNRESOLVED/REF]"

    def test_markup_subject_is_not_escaped_a_second_time(self, tmp_path: Path) -> None:
        # A str subclass: normalized to a bare str, finalize would escape it.
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        engine = self._engine(tmp_path, '{{ this | render("sub.md") }}', fmt)
        assert engine.render("t.md", Markup("already")) == "[already]"

    def test_non_template_safe_subject_is_still_rejected(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ this }}")
        with pytest.raises(TypeError, match="Non-inert value"):
            engine.render("t.md", object())


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
            output_format=MD,
            filters={"shout": shout},
        )
        assert engine.render("t.md", {}) == "HI"


class TestMakeEnvironment:
    """`make_environment` wires an OutputFormat's escape into the engine's
    finalizer hook.  It registers no filters / globals — the caller supplies
    those."""

    def test_applies_escape_to_bare_strings(self) -> None:
        fmt = OutputFormat(
            name="upper",
            escape=lambda s: s.upper(),
        )
        env = make_environment(fmt)
        assert env.render_str("{{ value }}", value="hello") == "HELLO"

    def test_passes_markup_through_without_escape(self) -> None:
        fmt = OutputFormat(
            name="upper",
            escape=lambda s: s.upper(),
        )
        env = make_environment(fmt)
        assert env.render_str("{{ value }}", value=Markup("hello")) == "hello"

    def test_renders_none_as_empty_string(self) -> None:
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        assert env.render_str("[{{ value }}]", value=None) == "[]"

    def test_renders_an_unbound_name_as_empty_string(self) -> None:
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        assert env.render_str("[{{ missing }}]") == "[]"

    def test_renders_a_broken_chain_as_empty_string(self) -> None:
        # Chainable undefined: a missing step part-way through keeps resolving
        # instead of raising, and what falls out renders as nothing.
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        assert env.render_str("[{{ a.b.c }}]", a={}) == "[]"

    def test_does_not_auto_escape_by_template_extension(self) -> None:
        # Escaping is the format's, via the finalizer.  The engine's own
        # auto-escape keys off the template name, so an `.html` one must not
        # pull HTML escaping in on top.
        fmt = OutputFormat(name="upper", escape=lambda s: s.upper())
        env = make_environment(fmt)
        assert env.render_str("{{ value }}", "t.html", value="a<b") == "A<B"

    def test_filter_returning_markup_bypasses_finalize_escape(self) -> None:
        # The finalizer escapes bare strings but passes Markup through; a
        # filter (registered by the caller, not the env) that returns Markup
        # must therefore survive unescaped.
        def raw(v: object) -> Markup:
            return Markup(str(v))

        env = make_environment(OutputFormat(name="upper", escape=lambda s: s.upper()))
        env.add_filter("raw", raw)
        assert env.render_str("{{ 'hi' | raw }}") == "hi"

    def test_python_methods_are_not_reachable(self) -> None:
        # pycompat is off, so the Python resemblance stops at the syntax: a
        # value carries no Python methods, and reaching for one is an error
        # naming the method rather than a silent empty render.
        env = make_environment(OutputFormat(name="plain", escape=lambda s: s))
        with pytest.raises(TemplateError, match="startswith"):
            env.render_str("{{ value.startswith('a') }}", value="ab")

    def test_string_prefix_suffix_are_reached_as_tests(self) -> None:
        # What replaces the dropped methods, and what the meta templates use.
        env = make_environment(OutputFormat(name="plain", escape=lambda s: s))
        template = "{{ value is startingwith('a') }}|{{ value is endingwith('b') }}"
        assert env.render_str(template, value="ab") == "True|True"


class TestTemplateEngineMdEscape:
    """End-to-end: TemplateEngine wires the `md` OutputFormat by default."""

    def test_escapes_bare_string_substitution(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value }}")
        engine = TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )
        assert engine.render("t.md", {"value": "a|b"}) == "a\\|b"

    def test_safe_filter_bypasses_escape(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ value | safe }}")
        engine = TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )
        assert engine.render("t.md", {"value": "# heading"}) == "# heading"


class TestPostProcess:
    """The engine applies the format's ``post_process`` to a rendered output,
    with the subject in hand.  Tested with a stand-in format to pin the seam
    independently of md's anchor stamp; the md behavior and both render paths
    are covered end-to-end in the md / render / generator tests."""

    def test_post_process_is_applied_to_render_output(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("body:{{ this }}")
        # A stand-in post-pass that wraps the output and echoes the subject.
        fmt = OutputFormat(
            name="wrap",
            escape=lambda s: s,
            post_process=lambda rendered, subject: f"[{subject}]{rendered}",
        )
        engine = TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=fmt, filters={}
        )
        assert engine.render("t.md", "X") == "[X]body:X"

    def test_default_post_process_is_identity(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("plain")
        # A bare format (no post_process set) leaves the output untouched.
        fmt = OutputFormat(name="bare", escape=lambda s: s)
        engine = TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=fmt, filters={}
        )
        assert engine.render("t.md", {}) == "plain"


class TestPathRegistry:
    """The bookkeeping behind one-page-per-path: a fresh out_path is
    claimable, an identical re-claim is a no-op, any other re-claim is a
    :class:`PageCollisionError`."""

    def test_first_claim_returns_true(self) -> None:
        assert PathRegistry().claim(Path("p.md"), {"id": "x"}, "a.md") is True

    def test_same_subject_and_template_is_noop(self) -> None:
        registry = PathRegistry()
        subject = {"id": "x"}
        registry.claim(Path("p.md"), subject, "a.md")
        # Same object (identity) and template: idempotent, do not rewrite.
        assert registry.claim(Path("p.md"), subject, "a.md") is False

    def test_different_subject_raises(self) -> None:
        registry = PathRegistry()
        registry.claim(Path("p.md"), {"id": "x"}, "a.md")
        # Equal-but-distinct object: identity differs, so it is a collision.
        with pytest.raises(PageCollisionError, match="p.md"):
            registry.claim(Path("p.md"), {"id": "x"}, "a.md")

    def test_different_template_raises(self) -> None:
        registry = PathRegistry()
        subject = {"id": "x"}
        registry.claim(Path("p.md"), subject, "a.md")
        with pytest.raises(PageCollisionError, match="'a.md' and 'b.md'"):
            registry.claim(Path("p.md"), subject, "b.md")

    def test_distinct_paths_are_independent(self) -> None:
        registry = PathRegistry()
        assert registry.claim(Path("p.md"), {"id": "x"}, "a.md") is True
        assert registry.claim(Path("q.md"), {"id": "y"}, "a.md") is True

    def test_collision_is_a_user_error_without_diagnostics(self) -> None:
        # A UserError so the pipeline renders its guidance, not a traceback;
        # no source anchor, so no diagnostic_entries.
        registry = PathRegistry()
        registry.claim(Path("p.md"), {"id": "x"}, "a.md")
        with pytest.raises(UserError) as exc_info:
            registry.claim(Path("p.md"), {"id": "x"}, "b.md")
        assert not hasattr(exc_info.value, "diagnostic_entries")
        assert exc_info.value.user_error_message == str(exc_info.value)


class TestEnvironmentPool:
    """The two properties the lending rests on: a live render never shares its
    Environment, and a finished one gives it back — raise or no raise."""

    def _pool(self) -> EnvironmentPool:
        fmt = OutputFormat(name="plain", escape=lambda s: s)
        return EnvironmentPool(lambda: make_environment(fmt))

    def test_nested_acquires_get_distinct_environments(self) -> None:
        pool = self._pool()
        with pool.acquire() as outer:
            with pool.acquire() as inner:
                assert outer is not inner

    def test_sequential_acquires_reuse_one_environment(self) -> None:
        # Sequential, not nested: nothing is in flight the second time, so the
        # first Environment comes back rather than a second being built.
        pool = self._pool()
        with pool.acquire() as first:
            pass
        with pool.acquire() as second:
            assert first is second

    def test_environment_returns_to_the_pool_when_the_render_raises(self) -> None:
        pool = self._pool()
        with pool.acquire() as first:
            pass
        with pytest.raises(RuntimeError):
            with pool.acquire():
                raise RuntimeError("render failed")
        # Had the failed render kept it, the pool would be empty here and a
        # second Environment would be built instead.
        with pool.acquire() as after:
            assert after is first


class TestRenderToFileIdempotency:
    """``render_to_file`` is wired to the registry: a fresh page is
    written, an identical repeat is skipped, a clobbering repeat raises."""

    def _engine(self, tmp_path: Path) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "a.md").write_text("A:{{ id }}")
        (templates_dir / "b.md").write_text("B:{{ id }}")
        return TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )

    def test_writes_new_path(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        engine.render_to_file("a.md", {"id": "x"}, Path("p.md"))
        assert (tmp_path / "p.md").read_text() == "A:x"

    def test_idempotent_repeat_is_noop(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        subject = {"id": "x"}
        engine.render_to_file("a.md", subject, Path("p.md"))
        engine.render_to_file("a.md", subject, Path("p.md"))
        assert (tmp_path / "p.md").read_text() == "A:x"

    def test_collision_propagates(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        subject = {"id": "x"}
        engine.render_to_file("a.md", subject, Path("p.md"))
        with pytest.raises(PageCollisionError):
            engine.render_to_file("b.md", subject, Path("p.md"))


class TestTemplateErrorConversion:
    """Both a template that will not parse and one that fails mid-render are
    the template author's to fix, so both become diagnostics."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.md").write_text(body)
        return TemplateEngine(
            tmp_path, templates_dir=templates_dir, output_format=MD, filters={}
        )

    def test_syntax_error_raises_file_validation_error(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "{{ unclosed")
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("bad.md", {})

        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].source == "minijinja"
        assert diags[0].line is not None
        assert "bad.md" in str(diags[0].file)

    def test_runtime_error_raises_file_validation_error(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path, "ok\n{{ value | no_such_filter }}")
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("bad.md", {"value": "x"})

        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].source == "minijinja"
        assert diags[0].line == 2
        # The file must resolve on disk, or the diagnostic cannot read its
        # snippet: the engine holds a template *name*, not a path.
        assert diags[0].file is not None and diags[0].file.is_file()

    def test_our_own_errors_are_not_swallowed(self, tmp_path: Path) -> None:
        # A Python exception raised by one of our filters is not a template
        # error and keeps its own type on the way out.
        def boom(value: object) -> str:
            raise UserError("filter said no")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "t.md").write_text("{{ 'x' | boom }}")
        engine = TemplateEngine(
            tmp_path,
            templates_dir=templates_dir,
            output_format=MD,
            filters={"boom": boom},
        )
        with pytest.raises(UserError, match="filter said no"):
            engine.render("t.md", {})


class TestAsTemplateHelper:
    """The intake half of the render boundary: what a template pipes in reaches
    a text processor as text, or not at all."""

    def test_coerces_a_non_str_subject(self) -> None:
        def bracket(text: str) -> str:
            return f"[{text}]"

        assert as_template_helper(bracket)(42) == "[42]"

    def test_absent_subject_skips_the_processor(self) -> None:
        calls: list[str] = []

        def record(text: str) -> str:
            calls.append(text)
            return text

        # `None` never reaches the processor: absence is `finalize`'s to render,
        # so no processor can stringify it into "None".
        assert as_template_helper(record)(None) is None
        assert calls == []

    def test_passes_further_arguments_through(self) -> None:
        def append(text: str, suffix: str) -> str:
            return f"{text}{suffix}"

        assert as_template_helper(append)("a", "!") == "a!"
