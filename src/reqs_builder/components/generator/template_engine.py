"""Template engine — Jinja2 rendering with {% section %} support.

Hides Jinja2 details behind a single `render` function.
"""

from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

from reqs_builder.components.generator.page_writer import PageWriter


class SectionProcessor(Protocol):
    def __call__(self, template_name: str, data: dict[str, Any]) -> str: ...


PROCESSOR_KEY = "_section_processor"


def render(
    template_name: str,
    templates_dir: Path,
    data: dict[str, Any],
    out_dir: Path,
) -> str:
    """Render a template with data and write section pages to out_dir."""
    env = Environment(
        extensions=[SectionExtension],
        keep_trailing_newline=True,
    )
    env.loader = FileSystemLoader(templates_dir)

    writer = PageWriter(
        out_dir=out_dir,
        render=lambda name, tdata: env.get_template(f"{name}.md").render(tdata),
    )
    env.globals[PROCESSOR_KEY] = writer  # type: ignore[assignment]

    return env.get_template(f"{template_name}.md").render(data)


class SectionExtension(Extension):
    """Jinja2 extension for {% section "template" with data %} tag."""

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
        processor: SectionProcessor = self.environment.globals[PROCESSOR_KEY]  # type: ignore[assignment]
        return processor(template_name, data)
