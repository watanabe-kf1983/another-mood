"""The project's Markdown parsing, with the operations that read a parse.

This module owns the single ``MarkdownIt`` instance.  A caller parses a body
once with :func:`parse` and hands the opaque :class:`ParsedMarkdown` to the
operations it needs — :func:`first_h1`, :func:`rewrite_inline_links` — so the
body is parsed only once and the token stream never leaves this module.

The two operations are the shared core under the preprocess prose pass (title
+ relative-link normalization) and the generator's ``relink`` filter (``node:``
→ URL).
"""

import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode


def _identity(url: str) -> str:
    return url


# The one parser.  normalizeLink is identity so a link href stays raw and
# matches the source byte-for-byte when splicing (rewrite_inline_links) — the
# default percent-encodes non-ASCII, and the encoded form would not match.
# Harmless for the AST inspection first_h1 does.
_MD = MarkdownIt()
_MD.normalizeLink = _identity  # type: ignore[method-assign]


@dataclass(frozen=True)
class ParsedMarkdown:
    """A parsed Markdown body: the source ``text`` and its token stream.

    Opaque to callers — obtain it from :func:`parse` and hand it back to this
    module's operations.  The tokens are an implementation detail and are not
    meant to be read outside this module.
    """

    text: str
    tokens: Sequence[Token]


def parse(text: str) -> ParsedMarkdown:
    """Parse a Markdown body once, for reuse across several operations."""
    return ParsedMarkdown(text=text, tokens=_MD.parse(text))


def first_h1(doc: ParsedMarkdown) -> str | None:
    """The text of the body's first H1 heading, or ``None`` if it has none."""
    tree = SyntaxTreeNode(doc.tokens)
    for node in tree.walk():
        if node.type == "heading" and node.tag == "h1":
            return node.children[0].content if node.children else None
    return None


def heading_nodes(doc: ParsedMarkdown) -> Sequence[Mapping[str, object]]:
    """The body's headings, in document order, as ``{id, title, level}`` nodes.

    Each heading becomes a link target: ``id`` is the GitHub-compatible slug of
    its text (see :func:`github_slug`), deduplicated within the body by a
    ``-N`` suffix; ``title`` is the raw heading source (matching :func:`first_h1`
    so an H1's node title equals the prose ``title``); ``level`` is 1–6.  All
    levels are kept — a heading carries a native id in every renderer, so a link
    may target any of them.
    """
    tree = SyntaxTreeNode(doc.tokens)
    used: set[str] = set()
    nodes: list[Mapping[str, object]] = []
    for node in tree.walk():
        if node.type == "heading":
            slug = _dedup(github_slug(_heading_text(node)), used)
            used.add(slug)
            title = node.children[0].content if node.children else ""
            nodes.append({"id": slug, "title": title, "level": int(node.tag[1:])})
    return nodes


def github_slug(text: str) -> str:
    r"""A GitHub-compatible heading slug for ``text``.

    Follows the algorithm GitHub documents for heading "Section links" —
    lower-case, spaces to ``-``, drop other whitespace and punctuation, keep the
    rest, and an ``-N`` suffix for duplicates (:func:`_dedup`); runs are not
    collapsed:
    https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links
    The exact keep-set — where that prose is loose (e.g. ``_`` is punctuation
    yet kept) — is Ruby ``\p{Word}`` (:func:`_is_word_char`), from GitHub's own
    open-sourced pipeline, html-pipeline's ``TableOfContentsFilter``
    (``/[^\p{Word}\- ]/u``):
    https://github.com/gjtorikian/html-pipeline/blob/f13a1534cb650ba17af400d1acd3a22c28004c09/lib/html/pipeline/toc_filter.rb
    """
    return "".join(
        "-" if ch in " -" else ch.lower() if _is_word_char(ch) else "" for ch in text
    )


def _is_word_char(ch: str) -> bool:
    r"""Whether ``ch`` is a Ruby ``\p{Word}`` character — GitHub's slug keep-set:
    a letter, a mark, a decimal digit, a letter-number (``Nl``, e.g. ``Ⅷ``), or
    connector punctuation (``Pc``, which includes ``_``).  Other numerics like
    ``①`` (``No``) are excluded.

    Spelled out by Unicode category because Python's ``re`` has no ``\p{...}``
    escape, and its ``\w`` is a different set — it keeps ``No`` and drops marks.
    """
    category = unicodedata.category(ch)
    return category[0] in ("L", "M") or category in ("Nd", "Nl", "Pc")


def _heading_text(node: SyntaxTreeNode) -> str:
    """A heading's plain text — the source the slug is derived from.

    Concatenates the visible text of its inline children (a code span
    contributes its literal content, ``node:`` → ``node``; emphasis / link
    markup contributes only its inner text), so the slug matches what the
    renderer sees rather than the raw Markdown.
    """
    return "".join(n.content for n in node.walk() if n.type in ("text", "code_inline"))


def _dedup(base: str, used: set[str]) -> str:
    """``base``, or ``base-N`` with the lowest ``N`` ≥ 1 free of ``used``.

    GitHub appends ``-1``, ``-2``, … to the second and later headings in a
    document that slug to the same id."""
    if base not in used:
        return base
    suffix = 1
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"


def rewrite_inline_links(
    doc: ParsedMarkdown, resolve: Callable[[str], str | None]
) -> str:
    """Rewrite each inline link's destination via ``resolve``.

    For each real inline link, ``resolve`` is called with its raw ``href`` and
    returns where the link should point: a new href retargets it, the same href
    leaves it unchanged, and ``None`` drops the destination — leaving a bare,
    conspicuous ``[text]``.  The link text is never touched.
    """
    text = doc.text
    # Splice right-to-left so each span (found on the original text) stays valid;
    # _find_inline_links yields in document order, so reversed() gives that.
    for link in reversed(list(_find_inline_links(doc.text, doc.tokens))):
        new_href = resolve(link.href)
        replacement = f"({new_href})" if new_href is not None else ""
        text = text[: link.start] + replacement + text[link.end :]
    return text


@dataclass(frozen=True)
class _Link:
    """A real inline link's destination: the raw ``href`` and the source span
    ``[start, end)`` covering its ``(href)`` (parentheses included).  The
    ``[text]`` before it and any bytes after it stay put."""

    href: str
    start: int
    end: int


def _find_inline_links(text: str, tokens: Sequence[Token]) -> Iterator[_Link]:
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
        for token in tokens
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
            yield _Link(href=href, start=sep + 1, end=end)
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
