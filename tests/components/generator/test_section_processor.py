"""Tests for section_processor — SectionExtension and SectionProcessorImpl."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jinja2 import DictLoader, Environment, TemplateSyntaxError

from another_mood.components.generator.section_processor import (
    PROCESSOR_KEY,
    SectionExtension,
    SectionProcessorImpl,
)


# -- Helpers --


@dataclass
class MockProcessor:
    """Records calls and returns a fixed string."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    return_value: str = ""

    def __call__(self, template_name: str, data: dict[str, Any]) -> str:
        self.calls.append((template_name, data))
        return self.return_value


def _make_extension_env(processor: MockProcessor) -> Environment:
    env = Environment(extensions=[SectionExtension], keep_trailing_newline=True)
    env.globals[PROCESSOR_KEY] = processor  # type: ignore[assignment]
    return env


# -- SectionExtension --


class TestSectionParsing:
    """Extension correctly parses template name and data from the tag."""

    def test_receives_template_name_and_data(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% section "profile" with user %}')
        template.render(user={"id": "alice", "name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][0] == "profile"
        assert mock.calls[0][1] == {"id": "alice", "name": "Alice"}

    def test_data_is_resolved_expression(self) -> None:
        """The with-expression is evaluated, not passed as a string."""
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% section "card" with items[0] %}')
        template.render(items=[{"id": "x", "val": 42}])

        assert mock.calls[0][1] == {"id": "x", "val": 42}

    def test_called_once_per_tag(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% section "a" with x %}{% section "b" with y %}')
        template.render(x={"id": "1"}, y={"id": "2"})

        assert len(mock.calls) == 2
        assert mock.calls[0][0] == "a"
        assert mock.calls[1][0] == "b"

    def test_inside_for_loop(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string(
            '{% for item in items %}{% section "detail" with item %}{% endfor %}'
        )
        template.render(items=[{"id": "a"}, {"id": "b"}, {"id": "c"}])

        assert len(mock.calls) == 3
        assert [c[1]["id"] for c in mock.calls] == ["a", "b", "c"]


class TestSectionOutput:
    """Extension returns renderer's output into the Jinja2 result."""

    def test_return_value_appears_in_output(self) -> None:
        mock = MockProcessor(return_value="REPLACED")
        env = _make_extension_env(mock)
        template = env.from_string('before{% section "x" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeREPLACEDafter"

    def test_empty_return_produces_nothing(self) -> None:
        mock = MockProcessor(return_value="")
        env = _make_extension_env(mock)
        template = env.from_string('before{% section "x" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeafter"


class TestSectionSyntaxError:
    def test_missing_with_keyword(self) -> None:
        env = _make_extension_env(MockProcessor())
        with pytest.raises(TemplateSyntaxError, match="expected token 'with'"):
            env.from_string('{% section "profile" user %}')


class TestSectionDataValidation:
    def test_accepts_dict_without_id(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% section "profile" with user %}')
        template.render(user={"name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][1] == {"name": "Alice"}

    def test_raises_on_non_dict(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% section "profile" with user %}')

        with pytest.raises(TypeError, match="got: str"):
            template.render(user="not a dict")


# -- SectionProcessorImpl --


class TestSectionProcessorImpl:
    def test_writes_file_to_correct_path(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").exists()

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "hi {{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").read_text() == "hi alice"

    def test_returns_empty_string(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"profile.md": "content"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        result = processor("profile", {"id": "alice"})

        assert result == ""

    def test_creates_subdirectory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"entity-detail.md": ""})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("entity-detail", {"id": "user"})

        assert (tmp_path / "entity-detail").is_dir()

    def test_multiple_pages_in_same_directory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"detail.md": "{{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("detail", {"id": "a"})
        processor("detail", {"id": "b"})

        assert (tmp_path / "detail" / "a.md").read_text() == "a"
        assert (tmp_path / "detail" / "b.md").read_text() == "b"

    def test_no_id_writes_flat_file(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"summary.md": "count={{ items|length }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("summary", {"items": [1, 2, 3]})

        assert (tmp_path / "summary.md").read_text() == "count=3"

    def test_no_id_does_not_create_subdirectory(self, tmp_path: Path) -> None:
        env = Environment(keep_trailing_newline=True)
        env.loader = DictLoader({"report.md": "ok"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("report", {"data": "value"})

        assert (tmp_path / "report.md").exists()
        assert not (tmp_path / "report").exists()
