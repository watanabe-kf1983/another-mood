# ``_out_path`` reads ``node._meta`` — a template-public field under the
# reserved ``_`` prefix (see data_tree.py), not a Python-protected attr.
# pyright: reportPrivateUsage=false
"""Mood-view processor — {% mood_view %} tag parsing and dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.reports_config import ReportsConfig

if TYPE_CHECKING:
    from another_mood.components.generator.template_engine import TemplateEngine

PROCESSOR_KEY = "_mood_view_processor"


@dataclass(frozen=True)
class MoodViewProcessorImpl:
    """Routes a {% mood_view %} invocation: inline expansion, or its own
    page via the engine at the subject's output path.

    Whether a subject splits is driven by ``file_per`` (see
    :meth:`_splits`)."""

    engine: TemplateEngine
    reports_config: ReportsConfig = ReportsConfig(file_per=())

    def __call__(self, template_name: str, subject: object) -> str:
        # Only a real data-tree node can become its own page; anything else
        # inlines.  The is-node check at the boundary lets _splits / _out_path
        # take a Node directly.
        if isinstance(subject, Node) and self._splits(subject):
            self.engine.render_to_file(template_name, subject, self._out_path(subject))
            return ""
        else:
            return self.engine.render(template_name, subject)

    def _splits(self, node: Node) -> bool:
        """Whether the node becomes its own page (else inlined): its
        ``object_type_id`` is a ``file_per`` split target."""
        return self.reports_config.is_split_target(node._meta.object_type_id)

    def _out_path(self, node: Node) -> Path:
        """Anchor-derived page path of a split node."""
        return Path(self.reports_config.page_path(node))


class MoodViewExtension(Extension):
    """Jinja2 extension for {% mood_view "template" with data %} tag."""

    tags = {"mood_view"}

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

    def _render(
        self,
        template_name: str,
        subject: object,
        caller: Any,
    ) -> str:
        processor = self.environment.globals[PROCESSOR_KEY]
        return processor(template_name, subject)  # type: ignore[return-value]
