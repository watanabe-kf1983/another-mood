"""Tests for mood_view_processor — MoodViewExtension and MoodViewProcessorImpl."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, TemplateSyntaxError

from another_mood.components.generator.mood_view_processor import (
    PROCESSOR_KEY,
    MoodViewExtension,
    MoodViewProcessorImpl,
)
from another_mood.components.generator.template_engine import TemplateEngine


# -- Helpers --


@dataclass
class MockProcessor:
    """Records calls and returns a fixed string."""

    calls: list[tuple[str, dict[str, Any], bool]] = field(default_factory=lambda: [])
    return_value: str = ""

    def __call__(
        self, template_name: str, data: dict[str, Any], *, inline: bool = False
    ) -> str:
        self.calls.append((template_name, data, inline))
        return self.return_value


def _make_extension_env(processor: MockProcessor) -> Environment:
    env = Environment(extensions=[MoodViewExtension], keep_trailing_newline=True)
    env.globals[PROCESSOR_KEY] = processor  # type: ignore[assignment]
    return env


# -- MoodViewExtension --


class TestMoodViewParsing:
    """Extension correctly parses template name and data from the tag."""

    def test_receives_template_name_and_data(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user %}')
        template.render(user={"id": "alice", "name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][0] == "profile.md"
        assert mock.calls[0][1] == {"id": "alice", "name": "Alice"}

    def test_data_is_resolved_expression(self) -> None:
        """The with-expression is evaluated, not passed as a string."""
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "card.md" with items[0] %}')
        template.render(items=[{"id": "x", "val": 42}])

        assert mock.calls[0][1] == {"id": "x", "val": 42}

    def test_called_once_per_tag(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string(
            '{% mood_view "a.md" with x %}{% mood_view "b.md" with y %}'
        )
        template.render(x={"id": "1"}, y={"id": "2"})

        assert len(mock.calls) == 2
        assert mock.calls[0][0] == "a.md"
        assert mock.calls[1][0] == "b.md"

    def test_inside_for_loop(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string(
            '{% for item in items %}{% mood_view "detail.md" with item %}{% endfor %}'
        )
        template.render(items=[{"id": "a"}, {"id": "b"}, {"id": "c"}])

        assert len(mock.calls) == 3
        assert [c[1]["id"] for c in mock.calls] == ["a", "b", "c"]


class TestMoodViewInlineKeyword:
    """The optional `inline` keyword forces the processor into inline mode."""

    def test_default_is_not_inline(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user %}')
        template.render(user={"id": "alice"})

        assert mock.calls[0][2] is False

    def test_inline_keyword_sets_flag(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user inline %}')
        template.render(user={"id": "alice"})

        assert mock.calls[0][2] is True

    def test_inline_return_value_appears_in_output(self) -> None:
        mock = MockProcessor(return_value="INLINED")
        env = _make_extension_env(mock)
        template = env.from_string('before{% mood_view "x.md" with d inline %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeINLINEDafter"


class TestMoodViewOutput:
    """Extension returns renderer's output into the Jinja2 result."""

    def test_return_value_appears_in_output(self) -> None:
        mock = MockProcessor(return_value="REPLACED")
        env = _make_extension_env(mock)
        template = env.from_string('before{% mood_view "x.md" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeREPLACEDafter"

    def test_empty_return_produces_nothing(self) -> None:
        mock = MockProcessor(return_value="")
        env = _make_extension_env(mock)
        template = env.from_string('before{% mood_view "x.md" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeafter"


class TestMoodViewSyntaxError:
    def test_missing_with_keyword(self) -> None:
        env = _make_extension_env(MockProcessor())
        with pytest.raises(TemplateSyntaxError, match="expected token 'with'"):
            env.from_string('{% mood_view "profile.md" user %}')


class TestMoodViewDataValidation:
    def test_accepts_dict_without_id(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user %}')
        template.render(user={"name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][1] == {"name": "Alice"}

    def test_raises_on_non_dict(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user %}')

        with pytest.raises(TypeError, match="got: str"):
            template.render(user="not a dict")


# -- MoodViewProcessorImpl --


@dataclass
class _MockEngine:
    """Captures calls to render / render_to_file for routing assertions."""

    rendered: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    written: list[tuple[str, dict[str, Any], Path]] = field(default_factory=lambda: [])
    render_return: str = "INLINED"

    def render(self, template_name: str, data: dict[str, Any]) -> str:
        self.rendered.append((template_name, data))
        return self.render_return

    def render_to_file(
        self, template_name: str, data: dict[str, Any], out_path: Path
    ) -> None:
        self.written.append((template_name, data, out_path))


class TestMoodViewProcessorImplRouting:
    """Processor computes the out_dir-relative out_path and delegates to engine."""

    def test_non_inline_with_id_writes_to_stem_subdirectory(self) -> None:
        engine = _MockEngine()
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        processor("profile.md", {"id": "alice", "name": "Alice"})

        assert engine.written == [
            (
                "profile.md",
                {"id": "alice", "name": "Alice"},
                Path("profile/alice.md"),
            ),
        ]
        assert engine.rendered == []

    def test_non_inline_without_id_writes_to_template_name(self) -> None:
        engine = _MockEngine()
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        processor("summary.md", {"items": [1, 2, 3]})

        assert engine.written == [
            ("summary.md", {"items": [1, 2, 3]}, Path("summary.md")),
        ]

    def test_non_inline_returns_empty_string(self) -> None:
        engine = _MockEngine()
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        result = processor("profile.md", {"id": "alice"})

        assert result == ""

    def test_inline_delegates_to_render(self) -> None:
        engine = _MockEngine(render_return="hi alice")
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        result = processor("profile.md", {"id": "alice"}, inline=True)

        assert engine.rendered == [("profile.md", {"id": "alice"})]
        assert engine.written == []
        assert result == "hi alice"


class TestMoodViewProcessorImplViaEngine:
    """End-to-end via a real TemplateEngine — exercises the integration."""

    def _make_engine(self, tmp_path: Path, templates: dict[str, str]) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        for name, body in templates.items():
            (templates_dir / name).write_text(body)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        return TemplateEngine(out_dir, templates_dir=templates_dir, filters={})

    def test_writes_file_with_rendered_content(self, tmp_path: Path) -> None:
        engine = self._make_engine(tmp_path, {"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(engine=engine)
        processor("profile.md", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "out" / "profile" / "alice.md").read_text() == "hi alice"

    def test_inline_does_not_write_file(self, tmp_path: Path) -> None:
        engine = self._make_engine(tmp_path, {"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(engine=engine)
        result = processor("profile.md", {"id": "alice"}, inline=True)

        assert result == "hi alice"
        assert not (tmp_path / "out" / "profile" / "alice.md").exists()
