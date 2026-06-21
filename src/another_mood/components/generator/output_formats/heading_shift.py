"""Shift a Markdown fragment's headings to nest under an enclosing level.

This is the string transform; ``md.py`` exposes it as the ``under_heading``
template filter, adapting the filter boundary (coercing the piped value to
``str``, marking the result safe).

The generation-time counterpart of the parser's H1 normalization: that
normalization levels a fragment's headings so its top is H1; this shifts
that fragment down to sit under the heading the author wrote it beneath.
The shift composes additively across nested embeds — each boundary shifts
only its own direct output by one level's worth, so cumulative depth never
has to be threaded through.

The shift works off the Markdown AST (markdown-it-py), not a raw ``^#+``
substitution: only real ATX heading nodes are rewritten, which is what lets
authors write literal ``#`` headings freely.  Which headings qualify and how
each is rewritten are documented on the functions below.
"""

from collections.abc import Iterator

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

# One module-level parser, reused across calls (matches source_loader._MD).
# MarkdownIt.parse() is reentrant: it builds a fresh StateCore per call and only
# reads the instance (no plugins mutate it), so the shared instance is safe even
# under the concurrent rebuilds `mood watch` can trigger.
_MD = MarkdownIt()

_MAX_LEVEL = 6


def under_heading(text: str, marker: str) -> str:
    """Shift each of ``text``'s outline headings down by the depth ``marker`` names.

    ``marker`` is the enclosing heading level as the author sees it at the call
    site — a run of ``#`` such as ``"##"`` — and its length is the shift added
    to each heading (clamped at H6), so a fragment written from ``#`` lands
    directly under that heading.  Only the fragment's own top-level headings
    move: a heading quoted in a blockquote or nested in a list, a setext
    heading, and ``#`` inside a code fence are left untouched.
    """
    shift = _shift_amount(marker)
    levels = dict(_atx_heading_lines(text))  # line index -> current heading level
    lines = [
        _deepen_marker(line, levels[i], shift) if i in levels else line
        for i, line in enumerate(text.split("\n"))
    ]
    return "\n".join(lines)


def _shift_amount(marker: str) -> int:
    """The shift named by ``marker``: the length of a non-empty run of ``#``.

    A marker with any other character is a template-author mistake (e.g.
    ``under_heading("h2")``), so it fails loudly rather than silently
    no-op'ing.
    """
    if not marker or set(marker) != {"#"}:
        raise ValueError(
            f"under_heading() expects a run of '#' naming the enclosing "
            f"heading level (e.g. '##'), got {marker!r}"
        )
    return len(marker)


def _deepen_marker(line: str, level: int, shift: int) -> str:
    """Rewrite the ATX marker on heading ``line`` to ``level + shift``, capped at H6.

    The cap collapses an over-shifted heading onto H6 rather than emitting an
    unrepresentable ``#######``.
    """
    # `level` (from the parser) is the marker length, so the `#` run sits right
    # after the indent; slicing past it keeps any trailing closing `##`.
    start = line.index("#")
    new_level = min(_MAX_LEVEL, level + shift)
    return line[:start] + "#" * new_level + line[start + level :]


def _atx_heading_lines(text: str) -> Iterator[tuple[int, int]]:
    """Yield ``(line_index, level)`` for each of ``text``'s outline headings.

    The outline is the top-level ATX headings — not ones nested in a blockquote
    or list.  See :func:`under_heading` for the author-facing effect.
    """
    tree = SyntaxTreeNode(_MD.parse(text))
    # tree.children are the document's direct children only, so nested headings
    # (blockquote, list) are already excluded; the `if` then keeps ATX nodes
    # (markup all `#`) and drops setext (markup `=` / `-`).
    return (
        (node.map[0], len(node.markup))
        for node in tree.children
        if node.type == "heading" and set(node.markup) == {"#"} and node.map
    )
