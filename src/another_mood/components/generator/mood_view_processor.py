"""Mood-view processor — {% mood_view %} tag and page writing.

Owns the entire mood_view concept: Jinja2 tag parsing, data validation,
template rendering, and file output.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

PROCESSOR_KEY = "_mood_view_processor"


def install(env: Environment, out_dir: Path) -> None:
    """Wire mood_view processing into a Jinja2 Environment.

    Must be called after env.loader is set, since the processor
    uses the environment to render sub-templates.
    """
    env.globals[PROCESSOR_KEY] = MoodViewProcessorImpl(env=env, out_dir=out_dir)  # type: ignore[assignment]


@dataclass(frozen=True)
class MoodViewProcessorImpl:
    env: Environment
    out_dir: Path

    def __call__(
        self, template_name: str, data: dict[str, Any], *, inline: bool = False
    ) -> str:
        rendered = self.env.get_template(f"{template_name}.md").render(data)
        if inline:
            return rendered
        if "id" in data:
            out_file = self.out_dir / template_name / f"{data['id']}.md"
        else:
            out_file = self.out_dir / f"{template_name}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered)
        return ""


class MoodViewExtension(Extension):
    """Jinja2 extension for {% mood_view "template" with data [inline] %} tag."""

    tags = {"mood_view"}

    def parse(self, parser: Parser) -> nodes.Node:
        lineno = next(parser.stream).lineno
        template_name = parser.parse_expression()
        parser.stream.expect("name:with")
        data = parser.parse_expression()
        inline = parser.stream.skip_if("name:inline")

        return nodes.CallBlock(
            self.call_method("_render", [template_name, data, nodes.Const(inline)]),
            [],
            [],
            [],
        ).set_lineno(lineno)

    def _render(
        self,
        template_name: str,
        data: dict[str, Any],
        inline: bool,
        caller: Any,
    ) -> str:
        if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                f'{{% mood_view "{template_name}" with ... %}} requires a dict, '
                f"got: {type(data).__name__}"
            )
        processor = self.environment.globals[PROCESSOR_KEY]
        return processor(template_name, data, inline=inline)  # type: ignore[return-value]
