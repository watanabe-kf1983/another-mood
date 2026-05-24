"""Tests for mood_view_processor — MoodViewExtension and MoodViewProcessorImpl."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jinja2 import DictLoader, Environment, TemplateSyntaxError

from another_mood.components.generator.mood_view_processor import (
    PROCESSOR_KEY,
    MoodViewExtension,
    MoodViewProcessorImpl,
)


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


class TestMoodViewProcessorImpl:
    def test_writes_file_to_correct_path(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile.md", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").exists()

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile.md", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").read_text() == "hi alice"

    def test_returns_empty_string(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "content"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        result = processor("profile.md", {"id": "alice"})

        assert result == ""

    def test_creates_subdirectory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"entity-detail.md": ""})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("entity-detail.md", {"id": "user"})

        assert (tmp_path / "entity-detail").is_dir()

    def test_multiple_pages_in_same_directory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"detail.md": "{{ id }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("detail.md", {"id": "a"})
        processor("detail.md", {"id": "b"})

        assert (tmp_path / "detail" / "a.md").read_text() == "a"
        assert (tmp_path / "detail" / "b.md").read_text() == "b"

    def test_no_id_writes_flat_file(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"summary.md": "count={{ items|length }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("summary.md", {"items": [1, 2, 3]})

        assert (tmp_path / "summary.md").read_text() == "count=3"

    def test_no_id_does_not_create_subdirectory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"report.md": "ok"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("report.md", {"data": "value"})

        assert (tmp_path / "report.md").exists()
        assert not (tmp_path / "report").exists()

    def test_inline_returns_rendered_content(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        result = processor("profile.md", {"id": "alice"}, inline=True)

        assert result == "hi alice"

    def test_inline_does_not_write_file(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile.md", {"id": "alice"}, inline=True)

        assert not (tmp_path / "profile" / "alice.md").exists()
        assert not (tmp_path / "profile").exists()
