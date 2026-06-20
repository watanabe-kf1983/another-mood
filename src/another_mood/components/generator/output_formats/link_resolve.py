"""Rewrite ``node:`` link destinations in a Markdown body.

A body carries inline links to a ``node:`` anchor path (``[text](node:/…)``).
:func:`resolve_links` rewrites each ``(node:/path)`` destination via a
caller-supplied renderer, splicing into the source so the link text and the rest
stay byte-for-byte.  Only the inline ``[text](node:…)`` form is handled.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token

# Used only to locate links (reused across calls; parse is reentrant).
# normalizeLink is identity so a href stays raw and matches the body to splice:
# the default percent-encodes non-ASCII, and the encoded form would not.
_MD = MarkdownIt()


def _identity(url: str) -> str:
    return url


_MD.normalizeLink = _identity  # type: ignore[method-assign]

_SCHEME = "node:"


def resolve_links(text: str, render_dest: Callable[[str], str]) -> str:
    """Rewrite each inline ``node:`` link's destination via ``render_dest``.

    For every ``[text](node:/anchor/path)``, the ``(node:/path)`` destination is
    replaced by ``render_dest(anchor_path)`` — a resolved ``(url)``, or ``""`` to
    drop it (leaving a plain ``[text]``).  The link text is never touched.
    """
    # Splice right-to-left so each span (found on the original text) stays valid;
    # _node_links yields in document order, so reversed() gives that.
    for link in reversed(list(_node_links(text))):
        text = text[: link.start] + render_dest(link.anchor_path) + text[link.end :]
    return text


@dataclass(frozen=True)
class _NodeLink:
    """The source span ``[start, end)`` of a ``(node:/path)`` destination and the
    ``anchor_path`` it points at.  The ``]`` and link text before it stay put."""

    anchor_path: str
    start: int
    end: int


def _node_links(text: str) -> Iterator[_NodeLink]:
    """Locate each real inline ``node:`` link's ``(node:/path)`` destination.

    A ``link_open`` token carries no source offset, so each ``](href)`` is found
    by searching its block's character window — bounded to the block so the same
    path in a code example elsewhere is not matched, and cursor-advanced so
    repeated links match successive occurrences.

    Residual edge: a real ``node:`` link and an inline-code span with the same
    literal ``](node:/path)`` in one block — the text search may hit the code one.
    """
    line_offsets = _line_offsets(text)
    blocks = [
        (token, token.map)
        for token in _MD.parse(text)
        if token.type == "inline" and token.map is not None
    ]
    for token, line_span in blocks:
        start_line, end_line = line_span  # end_line is exclusive
        window_start = line_offsets[start_line]
        window_end = (
            line_offsets[end_line] if end_line < len(line_offsets) else len(text)
        )
        cursor = window_start
        for href in _node_hrefs(token):
            needle = f"]({href})"
            sep = text.find(needle, cursor, window_end)
            if sep == -1:  # not an inline link (reference / autolink)
                continue
            end = sep + len(needle)
            # The `(href)` runs from just past the `]` through the `)`.
            yield _NodeLink(anchor_path=href[len(_SCHEME) :], start=sep + 1, end=end)
            cursor = end


def _node_hrefs(token: Token) -> Iterator[str]:
    """Yield the raw ``node:`` href of each real inline link in ``token``.

    Only ``link_open`` children qualify, so a ``node:`` inside inline code is
    excluded."""
    for child in token.children or ():
        href = child.attrs.get("href")
        if child.type == "link_open" and _is_node_ref(href):
            yield str(href)


def _line_offsets(text: str) -> list[int]:
    """Char offset where each line starts, to turn a token's line ``.map`` into a
    character window into ``text``."""
    offsets: list[int] = []
    position = 0
    for line in text.split("\n"):
        offsets.append(position)
        position += len(line) + 1  # + 1 for the "\n" that split() removed
    return offsets


def _is_node_ref(href: object) -> bool:
    return isinstance(href, str) and href.startswith(_SCHEME)
