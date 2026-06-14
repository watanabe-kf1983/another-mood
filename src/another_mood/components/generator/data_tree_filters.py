# ``_meta`` is a template-public node field under the reserved ``_`` prefix
# (see data_tree.py), not a Python-protected attribute.
# pyright: reportPrivateUsage=false
"""Data-tree Jinja2 filters — turning a reference into a linkable node, its
display text, and the page-relative URL to it.

All output-format-neutral: the filters that render these as markdown
(``href`` / ``link``) live with the md format; :func:`make_data_tree_filters`
here exposes only the neutral ones (``node`` / ``label``).  An unresolved
reference becomes a :class:`MissingNode` rather than an error, so a broken
link can render visibly instead of crashing.
"""

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.data_tree import child as node_child
from another_mood.components.generator.reports_config import ReportsConfig
from another_mood.components.generator.url import url_escape


def make_data_tree_filters(
    node_map: Mapping[str, Node],
) -> tuple[
    Mapping[str, Callable[..., object]],
    Mapping[str, Callable[..., object]],
]:
    """The format-neutral data-tree filters, bound to one build's node map.

    Returns ``(globals, filters)``: ``node`` works both as a call
    (``node("a", b)``) and a pipe (``"/a/b" | node``) so appears in both;
    ``label`` is a filter only.
    """

    def node(seg: object, *segs: object) -> object:
        return resolve_node(node_map, seg, *segs)

    globals_map: Mapping[str, Callable[..., object]] = {
        "node": node,
    }
    filters_map: Mapping[str, Callable[..., object]] = {
        "node": node,
        "label": node_label,
        "child": child,
    }
    return globals_map, filters_map


@dataclass(frozen=True)
class MissingNode:
    """Stands in for a reference that did not resolve, carrying the attempted
    path so a renderer can show it visibly."""

    anchor_path: str

    def __str__(self) -> str:
        return self.anchor_path


def resolve_node(node_map: Mapping[str, Node], seg: object, *segs: object) -> object:
    """Resolve segments / a ready-made path to its node, or a MissingNode."""
    path = build_anchor_path(seg, *segs)
    node = node_map.get(path)
    return node if node is not None else MissingNode(path)


def build_anchor_path(seg: object, *segs: object) -> str:
    """Anchor path from segments (each escaped), or a ready-made ``/``-leading
    path returned verbatim (e.g. a prose id or constant).

    A built segment is always an entity or query name, which cannot start
    with ``/``, so the leading-``/`` test separates ready-made from built
    unambiguously.
    """
    if not segs and isinstance(seg, str) and seg.startswith("/"):
        return seg
    return "/" + "/".join(url_escape(str(p), safe="") for p in (seg, *segs))


def child(parent: object, seg: object) -> object:
    """The ``child`` filter (``parent | child(seg)``): the relative
    counterpart to ``node``'s absolute lookup.

    Wraps :func:`data_tree.child`, mapping an unresolved step — a non-node
    parent or no matching child — to a :class:`MissingNode` carrying the
    attempted path, so it renders visibly instead of raising.
    """
    if not isinstance(parent, Node):
        # Nothing to step from (e.g. a chained-off MissingNode); the
        # attempted path is just the bare segment.
        return MissingNode(str(seg))
    if (found := node_child(parent, seg)) is not None:
        return found
    else:
        return MissingNode(_child_path(parent, seg))


def _child_path(parent: Node, seg: object) -> str:
    """The anchor path the unresolved child would have had, for its MissingNode."""
    base = parent._meta.anchor_path
    sep = "" if base == "/" else "/"
    return f"{base}{sep}{seg}"


def node_label(a: object) -> str:
    """Display text for a node: first of ``title`` / ``name`` / ``id``
    present, else its anchor path.

    The trailing path segment is deliberately not a fallback — it is
    meaningful only for list elements / nested objects.
    """
    if isinstance(a, MissingNode):
        return a.anchor_path
    if isinstance(a, Mapping):
        fields = cast(Mapping[str, object], a)
        for key in ("title", "name", "id"):
            if key in fields:
                return str(fields[key])
    return cast(Node, a)._meta.anchor_path


def node_href(config: ReportsConfig, source: object, a: object) -> str:
    """Page-relative URL — path to the target's page plus its anchor-path
    fragment — from the ``source`` node's page.

    ``a`` must be a resolved node: a :class:`MissingNode` has no page, so
    the rendering filters intercept that case and never call this for one.
    """
    target = cast(Node, a)
    source_dir = posixpath.dirname(config.page_path(cast(Node, source))) or "."
    rel = posixpath.relpath(config.page_path(target), source_dir)
    return f"{rel}#{target._meta.anchor_path}"
