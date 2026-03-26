"""Tests for SectionExtension — Jinja2 integration layer.

Verify that the extension correctly parses {% section %} tags
and delegates to the renderer callable.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
from jinja2 import Environment, TemplateSyntaxError

from reqs_builder.components.generator.section_processor import (
    SectionExtension,
    PROCESSOR_KEY,
)


@dataclass
class MockProcessor:
    """Records calls and returns a fixed string."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    return_value: str = ""

    def __call__(self, template_name: str, data: dict[str, Any]) -> str:
        self.calls.append((template_name, data))
        return self.return_value


def _make_env(processor: MockProcessor) -> Environment:
    env = Environment(extensions=[SectionExtension], keep_trailing_newline=True)
    env.globals[PROCESSOR_KEY] = processor  # type: ignore[assignment]
    return env


class TestSectionParsing:
    """1) Extension correctly parses template name and data from the tag."""

    def test_receives_template_name_and_data(self) -> None:
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string('{% section "profile" with user %}')
        template.render(user={"id": "alice", "name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][0] == "profile"
        assert mock.calls[0][1] == {"id": "alice", "name": "Alice"}

    def test_data_is_resolved_expression(self) -> None:
        """The with-expression is evaluated, not passed as a string."""
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string('{% section "card" with items[0] %}')
        template.render(items=[{"id": "x", "val": 42}])

        assert mock.calls[0][1] == {"id": "x", "val": 42}

    def test_called_once_per_tag(self) -> None:
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string('{% section "a" with x %}{% section "b" with y %}')
        template.render(x={"id": "1"}, y={"id": "2"})

        assert len(mock.calls) == 2
        assert mock.calls[0][0] == "a"
        assert mock.calls[1][0] == "b"

    def test_inside_for_loop(self) -> None:
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string(
            '{% for item in items %}{% section "detail" with item %}{% endfor %}'
        )
        template.render(items=[{"id": "a"}, {"id": "b"}, {"id": "c"}])

        assert len(mock.calls) == 3
        assert [c[1]["id"] for c in mock.calls] == ["a", "b", "c"]


class TestSectionOutput:
    """2) Extension returns renderer's output into the Jinja2 result."""

    def test_return_value_appears_in_output(self) -> None:
        mock = MockProcessor(return_value="REPLACED")
        env = _make_env(mock)
        template = env.from_string('before{% section "x" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeREPLACEDafter"

    def test_empty_return_produces_nothing(self) -> None:
        mock = MockProcessor(return_value="")
        env = _make_env(mock)
        template = env.from_string('before{% section "x" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeafter"


class TestSectionSyntaxError:
    def test_missing_with_keyword(self) -> None:
        env = _make_env(MockProcessor())
        with pytest.raises(TemplateSyntaxError, match="expected token 'with'"):
            env.from_string('{% section "profile" user %}')


class TestSectionDataValidation:
    def test_raises_on_missing_id(self) -> None:
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string('{% section "profile" with user %}')

        with pytest.raises(TypeError, match='requires a dict with "id" key'):
            template.render(user={"name": "Alice"})

    def test_raises_on_non_dict(self) -> None:
        mock = MockProcessor()
        env = _make_env(mock)
        template = env.from_string('{% section "profile" with user %}')

        with pytest.raises(TypeError, match="got: str"):
            template.render(user="not a dict")
