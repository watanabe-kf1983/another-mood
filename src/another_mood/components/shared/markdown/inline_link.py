"""Locate and rewrite inline Markdown link destinations.

:func:`rewrite_inline_links` finds each real ``[text](href)`` link and replaces
its ``(href)`` destination via a caller-supplied renderer, leaving the link text
and the rest byte-for-byte.  Only the inline form is handled.  It is the shared
core under both the generator's ``link_resolve`` (``node:`` → URL) and the
preprocess link normalizer (relative path → ``node:``).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token


def _identity(url: str) -> str:
    return url


# Reused across calls (parse is reentrant).  normalizeLink is identity so an
# href stays raw and matches the source when splicing — the default
# percent-encodes non-ASCII, and the encoded form would not.
_MD = MarkdownIt()
_MD.normalizeLink = _identity  # type: ignore[method-assign]


@dataclass(frozen=True)
class InlineLink:
    """A real inline link's destination: the raw ``href`` and the source span
    ``[start, end)`` covering its ``(href)`` (parentheses included).  The
    ``[text]`` before it and any bytes after it stay put."""

    href: str
    start: int
    end: int


def rewrite_inline_links(text: str, render: Callable[[InlineLink], str | None]) -> str:
    """Rewrite each inline link's ``(href)`` destination via ``render``.

    For each real inline link, ``render`` is called with its :class:`InlineLink`.
    A returned string replaces the ``(href)`` span — e.g. ``(url)`` to retarget,
    or ``""`` to drop the destination and leave a bare ``[text]`` — while
    ``None`` leaves the link untouched.  The link text is never touched.
    """
    # Splice right-to-left so each span (found on the original text) stays valid;
    # _find_inline_links yields in document order, so reversed() gives that.
    for link in reversed(list(_find_inline_links(text))):
        replacement = render(link)
        if replacement is not None:
            text = text[: link.start] + replacement + text[link.end :]
    return text


def _find_inline_links(text: str) -> Iterator[InlineLink]:
    """Locate each real inline link's ``(href)`` destination, in document order.

    A ``link_open`` token carries no source offset, so each ``](href)`` is found
    by searching its block's character window — bounded to the block so the same
    path in a code example elsewhere is not matched, and cursor-advanced so
    repeated links match successive occurrences.

    Residual edge: a real link and an inline-code span with the same literal
    ``](href)`` in one block — the text search may hit the code one.
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
        for href in _link_hrefs(token):
            needle = f"]({href})"
            sep = text.find(needle, cursor, window_end)
            if sep == -1:  # not a bare inline link (reference / autolink / titled)
                continue
            end = sep + len(needle)
            # The `(href)` runs from just past the `]` through the `)`.
            yield InlineLink(href=href, start=sep + 1, end=end)
            cursor = end


def _link_hrefs(token: Token) -> Iterator[str]:
    """Yield the raw href of each real inline link in ``token``.

    Only ``link_open`` children qualify, so an href inside inline code is
    excluded."""
    for child in token.children or ():
        href = child.attrs.get("href")
        if child.type == "link_open" and isinstance(href, str):
            yield href


def _line_offsets(text: str) -> list[int]:
    """Char offset where each line starts, to turn a token's line ``.map`` into a
    character window into ``text``."""
    offsets: list[int] = []
    position = 0
    for line in text.split("\n"):
        offsets.append(position)
        position += len(line) + 1  # + 1 for the "\n" that split() removed
    return offsets
