# ``_meta`` is a template-public node field under the reserved ``_`` prefix
# (see data_tree.py), not a Python-protected attribute.
# pyright: reportPrivateUsage=false
"""Anchor resolution — turning a reference into a linkable node, its display
text, and the page-relative URL to it.

All output-format-neutral: the filters that render these as markdown
(``href`` / ``link``) live with the md format; :func:`make_anchor_filters`
here exposes only the neutral ones (``anchor`` / ``anchor_path`` /
``label``).  An unresolved reference becomes a :class:`MissingAnchor` rather
than an error, so a broken link can render visibly instead of crashing.
"""

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from markupsafe import Markup

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.reports_config import ReportsConfig
from another_mood.components.generator.url import url_escape


def make_anchor_filters(
    anchor_map: Mapping[str, Node],
) -> tuple[
    Mapping[str, Callable[..., object]],
    Mapping[str, Callable[..., object]],
]:
    """The format-neutral anchor filters, bound to one build's anchor map.

    Returns ``(globals, filters)``: ``anchor`` / ``anchor_path`` work both
    as calls (``anchor("a", b)``) and pipes (``"/a/b" | anchor``) so appear
    in both; ``label`` is a filter only.
    """

    def anchor(seg: object, *segs: object) -> object:
        return resolve_anchor(anchor_map, seg, *segs)

    def anchor_path(seg: object, *segs: object) -> Markup:
        # The path is already escaped; Markup stops finalize from escaping it
        # again (Markup is the engine's generic "already safe" marker).
        return Markup(build_anchor_path(seg, *segs))

    globals_map: Mapping[str, Callable[..., object]] = {
        "anchor": anchor,
        "anchor_path": anchor_path,
    }
    filters_map: Mapping[str, Callable[..., object]] = {
        "anchor": anchor,
        "anchor_path": anchor_path,
        "label": anchor_label,
    }
    return globals_map, filters_map


@dataclass(frozen=True)
class MissingAnchor:
    """Stands in for a reference that did not resolve, carrying the attempted
    path so a renderer can show it visibly."""

    anchor_path: str

    def __str__(self) -> str:
        return self.anchor_path


def resolve_anchor(
    anchor_map: Mapping[str, Node], seg: object, *segs: object
) -> object:
    """Resolve segments / a ready-made path to its node, or a MissingAnchor."""
    path = build_anchor_path(seg, *segs)
    node = anchor_map.get(path)
    return node if node is not None else MissingAnchor(path)


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


def anchor_label(a: object) -> str:
    """Display text for an anchor: first of ``title`` / ``name`` / ``id``
    present, else its anchor path.

    The trailing path segment is deliberately not a fallback — it is
    meaningful only for list elements / nested objects.
    """
    if isinstance(a, MissingAnchor):
        return a.anchor_path
    if isinstance(a, Mapping):
        fields = cast(Mapping[str, object], a)
        for key in ("title", "name", "id"):
            if key in fields:
                return str(fields[key])
    return cast(Node, a)._meta.anchor_path


def anchor_href(config: ReportsConfig, source: object, a: object) -> str:
    """Page-relative URL — path to the target's page plus its anchor-path
    fragment — from the ``source`` node's page.

    ``a`` must be a resolved node: a :class:`MissingAnchor` has no page, so
    the rendering filters intercept that case and never call this for one.
    """
    target = cast(Node, a)
    source_dir = posixpath.dirname(config.page_path(cast(Node, source))) or "."
    rel = posixpath.relpath(config.page_path(target), source_dir)
    return f"{rel}#{target._meta.anchor_path}"
