# ``_out_path`` reads ``node._meta`` — a template-public field under the
# reserved ``_`` prefix (see data_tree.py), not a Python-protected attr.
# pyright: reportPrivateUsage=false
"""Render processor — the ``render`` filter (``{{ subject | render("tpl") }}``)
and its dispatch: inline expansion, or the subject's own page."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jinja2 import nodes, pass_context
from jinja2.ext import Extension
from jinja2.parser import Parser
from jinja2.runtime import Context
from markupsafe import Markup

from another_mood.components.generator.data_tree import Node, nearest_ancestor
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)

PROCESSOR_KEY = "_render_processor"


class Renderer(Protocol):
    """What the processor needs of the template engine: rendering a
    subject inline, or out to a file."""

    def render(self, template_name: str, subject: object) -> str: ...

    def render_to_file(
        self, template_name: str, subject: object, out_path: Path
    ) -> None: ...


@dataclass(frozen=True)
class RenderProcessorImpl:
    """Routes a render invocation: inline expansion, or its own page
    via the engine at the subject's output path.

    Whether a subject splits is driven by ``file_per`` (see
    :meth:`_splits`)."""

    engine: Renderer
    paging: PagingPolicy = PagingPolicy()

    def __call__(self, template_name: str, subject: object) -> str:
        # Only a real data-tree node can become its own page; anything else
        # inlines.  The is-node check at the boundary lets _splits / _out_path
        # take a Node directly.
        if isinstance(subject, Node) and self._splits(subject):
            self.engine.render_to_file(template_name, subject, self._out_path(subject))
            return ""
        else:
            return self.engine.render(template_name, subject)

    @pass_context
    def render_filter(
        self, context: Context, subject: object, template_name: str
    ) -> Markup:
        """The ``render`` filter: ``{{ subject | render("tpl") }}``.

        A subtree-guard error points at the enclosing template
        (``context.name``) without a line — a filter has no source
        location at runtime.
        """
        _guard_subtree(subject, context.resolve("this"), context.name, None)
        # Markup, not str: a filter's return value passes through the
        # environment's finalize, and the already-rendered output must
        # not be escaped a second time.
        return Markup(self(template_name, subject))

    def _splits(self, node: Node) -> bool:
        """Whether the node becomes its own page (else inlined): its
        ``object_type_id`` is a ``file_per`` split target."""
        return self.paging.is_split_target(node._meta.object_type_id)

    def _out_path(self, node: Node) -> Path:
        """Anchor-derived page path of a split node."""
        return ensure_not_windows_reserved(Path(self.paging.page_path(node)))


class RenderExtension(Extension):
    """Jinja2 extension for the {% render "template" with data %} tag.

    Deprecated: superseded by the ``render`` filter.  The tag is kept only
    for live projects that still use it and is removed, extension and all,
    once they have migrated.  ``mood_view`` is registered as a silent alias:
    both tag names route through the same :meth:`parse` (which consumes
    whichever keyword opened the tag), so they are behaviourally identical."""

    tags = {"render", "mood_view"}

    def parse(self, parser: Parser) -> nodes.Node:
        lineno = next(parser.stream).lineno
        template_name = parser.parse_expression()
        parser.stream.expect("name:with")
        data = parser.parse_expression()

        # Pass the render context (for the host ``this``) and the tag's own
        # source location, baked in at parse time, so :meth:`_render` can point
        # a subtree-guard error at the exact ``{% render %}`` line.
        args: list[nodes.Expr] = [
            nodes.ContextReference(),
            template_name,
            data,
            nodes.Const(parser.filename),
            nodes.Const(lineno),
        ]
        return nodes.CallBlock(
            self.call_method("_render", args),
            [],
            [],
            [],
        ).set_lineno(lineno)

    def _render(
        self,
        context: Context,
        template_name: str,
        subject: object,
        filename: str | None,
        lineno: int,
        caller: Any,
    ) -> str:
        _guard_subtree(subject, context.resolve("this"), filename, lineno)
        processor = self.environment.globals[PROCESSOR_KEY]
        return processor(template_name, subject)  # type: ignore[return-value]


def _guard_subtree(
    subject: object, host: object, filename: str | None, lineno: int | None
) -> None:
    """Reject a render whose node subject lies outside the host's subtree,
    pointing the error at the invocation's source location (the tag knows
    its exact line; the filter only its template).

    A node is drawn on exactly one page fixed by its data position
    (``PagingPolicy.page_path``); link resolution rides on that invariant (a
    link's source page is ``page_path(this)``, its target ``page_path(target)``).
    Embedding a node off its home page breaks both its outgoing ``this``-keyed
    links (``relink`` / ``link`` / ``href``) and the anchor others link *to*.
    So the subject must be ``host``-or-a-descendant — checked structurally by
    walking ``_parent`` from the subject up to the host by identity.

    A non-node subject is exempt: it carries no anchor and no page identity of
    its own.  The exemption is only sound for a subtemplate that renders no
    ``this``-keyed content (no ``link`` / ``href`` / ``anchor`` / ``relink``,
    no stamped anchor) — one that re-looks-up and draws a node internally is
    outside this guard's reach and owns its own link correctness.
    """
    if not isinstance(subject, Node):
        return
    # ``is not None`` (not truthiness): an empty MappingNode / ArrayNode host is
    # a falsy dict / list, yet still a valid ancestor match.
    if (
        isinstance(host, Node)
        and nearest_ancestor(subject, lambda n: n is host) is not None
    ):
        return
    host_desc = (
        f"`this` ({host._meta.anchor_path})"
        if isinstance(host, Node)
        else "the host, which is not a data node"
    )
    raise FileValidationError(
        [
            Diagnostic(
                file=Path(filename) if filename else None,
                line=lineno,
                column=None,
                message=(
                    f"`render` can only render a node within its host's "
                    f"subtree, but {subject._meta.anchor_path} is not a descendant "
                    f"of {host_desc}. A node is drawn on exactly one page fixed by "
                    f"its data position, so embedding one off its home page breaks "
                    f"its links. Bring it into the subtree with a query (e.g. a "
                    f"join) so it becomes a descendant, or reference it with "
                    f"`| link` instead of embedding it."
                ),
                source="render",
            )
        ]
    )
