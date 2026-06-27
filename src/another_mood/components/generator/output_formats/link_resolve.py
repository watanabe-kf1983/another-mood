"""Rewrite ``node:`` link destinations in a Markdown body.

A body carries inline links to a ``node:`` anchor path (``[text](node:/…)``).
:func:`resolve_links` rewrites each ``(node:/path)`` destination via a
caller-supplied renderer, leaving the link text and the rest byte-for-byte.
Only the inline ``[text](node:…)`` form is handled; locating the inline links
is delegated to :mod:`another_mood.components.shared.markdown.inline_link`.
"""

from collections.abc import Callable

from another_mood.components.shared.markdown.inline_link import (
    InlineLink,
    rewrite_inline_links,
)

_SCHEME = "node:"


def resolve_links(text: str, render_dest: Callable[[str], str]) -> str:
    """Rewrite each inline ``node:`` link's destination via ``render_dest``.

    For every ``[text](node:/anchor/path)``, the ``(node:/path)`` destination is
    replaced by ``render_dest(anchor_path)`` — a resolved ``(url)``, or ``""`` to
    drop it (leaving a plain ``[text]``).  Links with any other scheme are left
    as-is, and the link text is never touched.
    """

    def render(link: InlineLink) -> str | None:
        if not link.href.startswith(_SCHEME):
            return None
        return render_dest(link.href[len(_SCHEME) :])

    return rewrite_inline_links(text, render)
