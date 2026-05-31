"""Mood-view processor — {% mood_view %} tag parsing and dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

if TYPE_CHECKING:
    from another_mood.components.generator.template_engine import TemplateEngine

PROCESSOR_KEY = "_mood_view_processor"


@dataclass(frozen=True)
class MoodViewProcessorImpl:
    """Routes {% mood_view %} invocations to TemplateEngine."""

    engine: TemplateEngine

    def __call__(
        self, template_name: str, data: dict[str, Any], *, inline: bool = False
    ) -> str:
        if inline:
            return self.engine.render(template_name, data)
        if "id" in data:
            out_path = Path(Path(template_name).stem) / f"{data['id']}.md"
        else:
            out_path = Path(template_name)
        self.engine.render_to_file(template_name, data, out_path)
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
