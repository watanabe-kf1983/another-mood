"""Prose preprocessing — derive prose record fields from its id and content.

The source loader wraps a Markdown file into a path-derived ``id`` and a raw
``content``, tagged by ``mime_type``; it does not interpret the Markdown.
``preprocess_prose`` does: for each Markdown prose record it derives a
``title`` from the first H1, collects its ``headings`` as link-target nodes,
rewrites the content's relative links to ``node:/prose/<id>`` form, and reads
the record's place in the folder tree (``order_key`` / ``depth``) off the id.
A record's Markdown-ness is detected by its ``mime_type``, never by file
extension.
"""

import posixpath
from collections.abc import Callable, Mapping
from typing import cast
from urllib.parse import SplitResult, urlsplit

from another_mood.components.shared.markdown import (
    first_h1,
    heading_nodes,
    parse,
    rewrite_inline_links,
)


def preprocess_prose(data: Mapping[str, object]) -> Mapping[str, object]:
    """Return ``data`` with each Markdown prose record's content interpreted.

    For every ``prose`` record with ``text/markdown`` content, derive a
    ``title`` (first H1, unless one is already set), collect its ``headings``
    as link-target nodes, rewrite the content's relative links to
    ``node:/prose/<id>`` form, and add its folder-tree ``order_key`` /
    ``depth``.  Records with non-Markdown content, and data without a
    list-valued ``prose`` collection, pass through unchanged.
    """
    return _map_prose_records(data, _interpret)


def normalize_links(content: str, doc_id: str) -> str:
    """Rewrite each relative Markdown link in ``content`` to its ``node:`` form.

    An inline link ``[text](relative/path.md)`` whose target resolves to a prose
    document inside the contents tree becomes ``node:/prose/<resolved-id>``,
    resolved lexically against ``doc_id`` (this document's contents-relative
    path, without extension); a ``#heading-slug`` fragment rides through
    verbatim (``node:/prose/<resolved-id>#heading-slug``).  Links that don't
    name an in-tree prose document are left byte-for-byte (see
    :func:`_resolver`).
    """
    return rewrite_inline_links(parse(content), _resolver(doc_id))


def _map_prose_records(
    data: Mapping[str, object],
    transform: Callable[[object], object],
) -> Mapping[str, object]:
    """Apply ``transform`` to every record under a list-valued ``prose`` key.

    Data without such a collection passes through unchanged.
    """
    match data:
        case {"prose": list()}:
            records = cast(list[object], data["prose"])
            return {**data, "prose": [transform(record) for record in records]}
        case _:
            return data


def _interpret(record: object) -> object:
    """Derive a prose record's fields in two independent passes.

    The passes match on what each needs, not on one another: ``order_key`` /
    ``depth`` come from the id, so *any* prose record gets them; ``title`` and
    the ``node:`` link rewrite come from Markdown content, so only those
    records get them.  A record lacking each pass's shape falls through that
    pass.
    """
    return _interpret_markdown(_add_outline(record))


def _add_outline(record: object) -> object:
    """Add the id-derived folder-tree fields (``order_key`` / ``depth``) to any
    record carrying an ``id``."""
    match record:
        case {"id": str(doc_id)}:
            order_key, depth = _outline_position(doc_id)
            mapping = cast(Mapping[str, object], record)
            return {**mapping, "order_key": order_key, "depth": depth}
        case _:
            return record


def _outline_position(doc_id: str) -> tuple[str, int]:
    """The ``(order_key, depth)`` of a prose id — its place in the folder tree.

    A trailing ``index`` segment marks a folder's own intro page: it sorts
    ahead of the folder's files (``order_key`` is the folder path ``".../"``,
    the root index ``""``) and sits one heading level above them (``depth`` is
    the segment count; a file is one deeper).  A plain string sort on
    ``order_key`` then yields folder pre-order — each folder's index first, its
    subtree contiguous — for provisional alphabetic ids and later
    numeric-prefixed ones alike.
    """
    *folders, leaf = doc_id.split("/")
    if leaf == "index":
        order_key = "/".join(folders) + "/" if folders else ""
        return order_key, len(folders) + 1
    return doc_id, len(folders) + 2


def _interpret_markdown(record: object) -> object:
    """Derive ``title`` / ``headings`` and rewrite links for a Markdown record.

    A first-H1 ``title`` is added only when the record has none (an existing
    one, any value, is kept); ``headings`` (the content's headings as
    link-target nodes, empty when there are none) is always added; relative
    links are rewritten to ``node:`` form.  Records with non-Markdown content
    pass through unchanged.
    """
    match record:
        case {
            "id": str(doc_id),
            "mime_type": "text/markdown",
            "content": str(content),
        }:
            mapping = cast(Mapping[str, object], record)
            doc = parse(content)
            normalized = rewrite_inline_links(doc, _resolver(doc_id))
            new_title = None if "title" in mapping else first_h1(doc)
            return {
                **mapping,
                "content": normalized,
                **({"title": new_title} if new_title is not None else {}),
                "headings": heading_nodes(doc),
            }
        case _:
            return record


# ── Link normalization ───────────────────────────────────────────────


_MARKDOWN_SUFFIX = ".md"
_NODE_PROSE_PREFIX = "node:/prose/"


def _resolver(doc_id: str) -> Callable[[str], str]:
    """Build the ``rewrite_inline_links`` callback for the document ``doc_id``.

    The callback converts an in-tree relative ``.md`` link to its
    ``node:/prose/<id>`` form — resolved against ``doc_id``'s directory, any
    ``#fragment`` (a heading slug) carried through verbatim — and echoes every
    other href back unchanged.
    """
    base = posixpath.dirname(doc_id)

    def resolve(href: str) -> str:
        link = urlsplit(href)
        if _is_relative_markdown(link):
            resolved = posixpath.normpath(posixpath.join(base, link.path))
            if not resolved.startswith("../"):  # stays inside the contents tree
                node = f"{_NODE_PROSE_PREFIX}{resolved[: -len(_MARKDOWN_SUFFIX)]}"
                return f"{node}#{link.fragment}" if link.fragment else node
        return href

    return resolve


def _is_relative_markdown(link: SplitResult) -> bool:
    """True if ``link`` is a relative path to a Markdown file.

    False for an external reference (a scheme like ``http:`` / ``node:`` /
    ``mailto:``, or a ``//host``), an absolute path (leading ``/``), and any
    non-``.md`` target — an image, a stylesheet, or a pure ``#fragment`` (whose
    path is empty).
    """
    return (
        not link.scheme
        and not link.netloc
        and not link.path.startswith("/")
        and link.path.lower().endswith(_MARKDOWN_SUFFIX)
    )
