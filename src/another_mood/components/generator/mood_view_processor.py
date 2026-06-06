"""Mood-view processor — {% mood_view %} tag parsing and dispatch."""

from __future__ import annotations

from collections.abc import Mapping
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
    """Routes a {% mood_view %} invocation: inline expansion, or its own
    page via the engine at the subject's output path."""

    engine: TemplateEngine

    def __call__(
        self, template_name: str, subject: object, *, inline: bool = False
    ) -> str:
        if inline:
            return self.engine.render(template_name, subject)
        else:
            self.engine.render_to_file(
                template_name, subject, self._out_path(template_name, subject)
            )
            return ""

    @staticmethod
    def _out_path(template_name: str, subject: object) -> Path:
        """Out_dir-relative page path for a split subject.

        ``{stem}/{id}.md`` for an id-bearing record, else ``template_name``
        for any other node (a record without ``id``, or a collection).  A
        scalar has no page, so it is rejected here — the only place that
        maps a subject to a page.  Interim until paging routes every
        subject through ``ReportsConfig.page_path(node)`` (paging-spec C3).
        """
        if isinstance(subject, Mapping) and "id" in subject:
            return Path(Path(template_name).stem) / f"{subject['id']}.md"
        elif isinstance(subject, (Mapping, list)):
            return Path(template_name)
        else:
            raise TypeError(
                f'{{% mood_view "{template_name}" with ... %}} writes a page, '
                f"so its subject must be a Mapping or Array, "
                f"got: {type(subject).__name__}"
            )


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
        subject: object,
        inline: bool,
        caller: Any,
    ) -> str:
        processor = self.environment.globals[PROCESSOR_KEY]
        return processor(template_name, subject, inline=inline)  # type: ignore[return-value]
