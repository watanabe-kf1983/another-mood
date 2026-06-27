"""Prose preprocessing — derive prose record fields from the Markdown body.

The source loader wraps a Markdown file into a path-derived ``id`` and a
raw ``body`` (``mime_type`` + ``content``); it does not interpret the
Markdown.  Interpreting that body — currently extracting a display
``title`` from the first H1 — is a data-driven concern, so it lives here
in preprocess.  This keeps the loader free of AST handling and keeps
preprocess free of file paths: detection is by ``body.mime_type``, never
by ``src_file`` extension, and both the ``id`` and the ``content`` are
read off the record.

Scope is limited to the ``prose`` collection for now; H3 generalizes
title derivation to every entity carrying a Markdown body.
"""

from collections.abc import Mapping
from typing import cast

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

# Module-level parser, reused across calls (matches heading_shift._MD).
_MD = MarkdownIt()


def derive_prose_titles(data: Mapping[str, object]) -> Mapping[str, object]:
    """Return ``data`` with a ``title`` derived for each Markdown prose record.

    For every record under ``prose`` whose ``body.mime_type`` is
    ``text/markdown``, a ``title`` is taken from the first H1 of
    ``body.content``.  Records that already carry a ``title``, lack a
    Markdown body, or have no H1 are left untouched.  Data without a
    list-valued ``prose`` collection passes through unchanged.
    """
    match data:
        case {"prose": list()}:
            records = cast(list[object], data["prose"])
            return {**data, "prose": [_with_title(record) for record in records]}
        case _:
            return data


def _with_title(record: object) -> object:
    """Attach a first-H1 ``title`` to an untitled Markdown prose record.

    Only a Markdown ``body`` (``mime_type`` text/markdown with string
    ``content``) is processed: an existing ``title`` key (any value) is
    kept, otherwise the first H1 of the content becomes the title (no H1
    → stays untitled).  Everything else — non-mapping, non-Markdown,
    malformed — falls through unchanged.

    The ``cast`` is sound because the mapping pattern has already
    confirmed a mapping at runtime; pyright simply does not narrow the
    ``match`` subject itself, so the type must be restated.
    """
    match record:
        case {"body": {"mime_type": "text/markdown", "content": str(content)}}:
            mapping = cast(Mapping[str, object], record)
            title = (
                mapping["title"] if "title" in mapping else _extract_h1_title(content)
            )
            return {**mapping, "title": title} if title is not None else mapping
        case _:
            return record


def _extract_h1_title(content: str) -> str | None:
    """Extract text from the first H1 heading using the Markdown AST."""
    tree = SyntaxTreeNode(_MD.parse(content))
    for node in tree.walk():
        if node.type == "heading" and node.tag == "h1":
            return node.children[0].content if node.children else None
    return None
