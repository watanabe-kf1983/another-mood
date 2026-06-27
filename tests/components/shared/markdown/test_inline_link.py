"""Tests for the shared inline-link rewriter.

These cover the primitive's own contract — the render trichotomy (retarget /
drop / decline), in-order splicing, and what is structurally out of scope (code,
non-bare destinations).  Caller-specific scenarios live with each caller's
tests (e.g. the ``node:`` policy in ``test_link_resolve.py``)."""

from another_mood.components.shared.markdown.inline_link import (
    InlineLink,
    rewrite_inline_links,
)


def _render(link: InlineLink) -> str | None:
    """Stand-in policy: retarget ``a.md``, drop ``gone``, decline the rest."""
    if link.href == "a.md":
        return "(A)"
    if link.href == "gone":
        return ""
    return None


class TestRewriteInlineLinks:
    """rewrite_inline_links: splice each link's ``(href)`` via the renderer."""

    def test_retargets_a_destination(self) -> None:
        assert rewrite_inline_links("see [x](a.md) ok", _render) == "see [x](A) ok"

    def test_drops_a_destination_to_bare_text(self) -> None:
        assert rewrite_inline_links("see [x](gone) ok", _render) == "see [x] ok"

    def test_declines_to_leave_a_link_untouched(self) -> None:
        src = "see [x](keep.md) ok"
        assert rewrite_inline_links(src, _render) == src

    def test_rewrites_multiple_links_in_order(self) -> None:
        # Mixed decisions across one block exercise the right-to-left splice.
        assert (
            rewrite_inline_links("[x](a.md) [y](gone) [z](keep.md)", _render)
            == "[x](A) [y] [z](keep.md)"
        )

    def test_excludes_code_spans_and_fences(self) -> None:
        # A fenced block and an inline-code span carry no link_open, so their
        # link-like text is never matched; the real link is still rewritten.
        text = "```\n[c](a.md)\n```\n\n`[c](b.md)` and [d](a.md)"
        assert rewrite_inline_links(text, _render) == (
            "```\n[c](a.md)\n```\n\n`[c](b.md)` and [d](A)"
        )

    def test_leaves_non_bare_destinations(self) -> None:
        # Reference-style and titled destinations are not the bare ``](href)``
        # needle, so they are left untouched rather than rewritten or crashed.
        assert rewrite_inline_links("see [x][r]\n\n[r]: a.md\n", _render) == (
            "see [x][r]\n\n[r]: a.md\n"
        )
        assert rewrite_inline_links('[x](a.md "Title")', _render) == '[x](a.md "Title")'
