"""Jinja2 Extension for {% section "template" with data %} tag.

Parses the tag and delegates rendering to a SectionProcessor callable.
"""

from typing import Any, Protocol

from jinja2 import Environment, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser


class SectionProcessor(Protocol):
    def __call__(self, template_name: str, data: dict[str, Any]) -> str: ...


_PROCESSOR_KEY = "_section_processor"


def make_section_env(processor: SectionProcessor) -> Environment:
    """Create a Jinja2 Environment with the section extension wired up."""
    env = Environment(
        extensions=[SectionExtension],
        keep_trailing_newline=True,
    )
    env.globals[_PROCESSOR_KEY] = processor  # type: ignore[assignment]
    return env


class SectionExtension(Extension):
    tags = {"section"}

    def parse(self, parser: Parser) -> nodes.Node:
        lineno = next(parser.stream).lineno
        template_name = parser.parse_expression()
        parser.stream.expect("name:with")
        data = parser.parse_expression()

        return nodes.CallBlock(
            self.call_method("_render", [template_name, data]),
            [],
            [],
            [],
        ).set_lineno(lineno)

    def _render(self, template_name: str, data: dict[str, Any], caller: Any) -> str:
        if not isinstance(data, dict) or "id" not in data:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                f'{{% section "{template_name}" with ... %}} requires a dict '
                f'with "id" key, got: {type(data).__name__}'
            )
        processor: SectionProcessor = self.environment.globals[_PROCESSOR_KEY]  # type: ignore[assignment]
        return processor(template_name, data)
