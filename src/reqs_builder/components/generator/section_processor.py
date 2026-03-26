"""Section processor — {% section %} tag and page writing.

Owns the entire "section" concept: Jinja2 tag parsing, data validation,
template rendering, and file output.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

RenderFn = Callable[[str, dict[str, Any]], str]

PROCESSOR_KEY = "_section_processor"


def install(env: Environment, out_dir: Path) -> None:
    """Wire section processing into a Jinja2 Environment.

    Must be called after env.loader is set, since the PageWriter
    uses the environment to render sub-templates.
    """
    writer = PageWriter(
        out_dir=out_dir,
        render=lambda name, data: env.get_template(f"{name}.md").render(data),
    )
    env.globals[PROCESSOR_KEY] = writer  # type: ignore[assignment]


@dataclass(frozen=True)
class PageWriter:
    out_dir: Path
    render: RenderFn

    def __call__(self, template_name: str, data: dict[str, Any]) -> str:
        rendered = self.render(template_name, data)
        out_file = self.out_dir / template_name / f"{data['id']}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered)
        return ""


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
        processor = self.environment.globals[PROCESSOR_KEY]
        return processor(template_name, data)  # type: ignore[return-value]
