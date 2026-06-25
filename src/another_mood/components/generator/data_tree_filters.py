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

    Returns ``(globals, filters)``.  ``node`` is a global only: it tells
    escaped positional segments from a verbatim ``path=`` by keyword, which a
    pipe (``x | node``) cannot carry.  ``label`` / ``child`` are filters.
    """

    def node(*segs: object, path: object = None) -> object:
        return resolve_node(node_map, *segs, path=path)

    globals_map: Mapping[str, Callable[..., object]] = {
        "node": node,
    }
    filters_map: Mapping[str, Callable[..., object]] = {
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


def resolve_node(
    node_map: Mapping[str, Node], *segs: object, path: object = None
) -> object:
    """Resolve an anchor path to its node, or a :class:`MissingNode`.

    ``path`` (a ready-made address) is a verbatim prefix; positional ``segs``
    are each escaped and appended, so the escape mode is visible at the call.
    Either alone works, and they compose — ``segs`` dig into ``path``'s
    children (``node("y", path="/prose/x")`` → ``/prose/x/y``).  A misused
    input is never an error: a ``/``-leading positional is escaped to
    ``/%2F…`` and, not matching, surfaces as a visible MissingNode — the same
    way any unresolved reference does, rather than crashing the page.
    """
    prefix = "" if path is None else str(path)
    anchor = prefix + build_anchor_path(*segs)
    node = node_map.get(anchor)
    return node if node is not None else MissingNode(anchor)


def build_anchor_path(*segs: object) -> str:
    """The segment part of an anchor path — each raw value IRI-escaped and
    ``/``-prefixed, joined.  Empty for no segments, so a verbatim ``path``
    prefix stands alone (see :func:`resolve_node`)."""
    return "".join("/" + url_escape(str(p), safe="") for p in segs)


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
