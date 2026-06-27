"""Tests for the shared Markdown module — parse, first_h1, rewrite_inline_links.

These cover each operation's own contract over a parsed body: the H1 lookup,
the resolve trichotomy (retarget / drop / decline), in-order splicing, and what
is structurally out of scope (code, non-bare destinations).  Caller-specific
scenarios live with each caller's tests (e.g. the ``node:`` policy in
``test_md.py``'s relink wiring, the relative-link policy in ``test_prose.py``)."""

from another_mood.components.shared.markdown import (
    first_h1,
    parse,
    rewrite_inline_links,
)


def _resolve(href: str) -> str | None:
    """Stand-in policy: retarget ``a.md``, drop ``gone`` (None), keep the rest
    unchanged by echoing the href back."""
    if href == "a.md":
        return "A"
    if href == "gone":
        return None
    return href


class TestFirstH1:
    """first_h1: the text of the body's first H1, or None."""

    def test_h1_at_beginning(self) -> None:
        assert first_h1(parse("# Title\n\nBody.\n\n## Section\n")) == "Title"

    def test_h1_at_end(self) -> None:
        assert first_h1(parse("Some intro text.\n\n# Late Title\n")) == "Late Title"

    def test_first_of_two_h1s(self) -> None:
        assert first_h1(parse("# First\n\nText.\n\n# Second\n")) == "First"

    def test_no_h1_is_none(self) -> None:
        assert first_h1(parse("Just plain text.\n")) is None

    def test_h2_is_not_an_h1(self) -> None:
        assert first_h1(parse("## Not a title\n\nContent.\n")) is None


class TestRewriteInlineLinks:
    """rewrite_inline_links: splice each link's ``(href)`` via the resolver."""

    def test_retargets_a_destination(self) -> None:
        assert rewrite_inline_links(parse("see [x](a.md) ok"), _resolve) == (
            "see [x](A) ok"
        )

    def test_drops_a_destination_to_bare_text(self) -> None:
        assert rewrite_inline_links(parse("see [x](gone) ok"), _resolve) == (
            "see [x] ok"
        )

    def test_keeps_a_link_whose_href_is_echoed(self) -> None:
        # resolve returns the href unchanged, so the link is re-spliced identically.
        src = "see [x](keep.md) ok"
        assert rewrite_inline_links(parse(src), _resolve) == src

    def test_rewrites_multiple_links_in_order(self) -> None:
        # Mixed decisions across one block exercise the right-to-left splice.
        assert (
            rewrite_inline_links(parse("[x](a.md) [y](gone) [z](keep.md)"), _resolve)
            == "[x](A) [y] [z](keep.md)"
        )

    def test_excludes_code_spans_and_fences(self) -> None:
        # A fenced block and an inline-code span carry no link_open, so their
        # link-like text is never matched; the real link is still rewritten.
        text = "```\n[c](a.md)\n```\n\n`[c](b.md)` and [d](a.md)"
        assert rewrite_inline_links(parse(text), _resolve) == (
            "```\n[c](a.md)\n```\n\n`[c](b.md)` and [d](A)"
        )

    def test_leaves_non_bare_destinations(self) -> None:
        # Reference-style and titled destinations are not the bare ``](href)``
        # needle, so they are left untouched rather than rewritten or crashed.
        assert rewrite_inline_links(parse("see [x][r]\n\n[r]: a.md\n"), _resolve) == (
            "see [x][r]\n\n[r]: a.md\n"
        )
        assert rewrite_inline_links(parse('[x](a.md "Title")'), _resolve) == (
            '[x](a.md "Title")'
        )


class TestParseSharedAcrossOperations:
    """One parse feeds both operations — the path a multi-derivation caller uses."""

    def test_first_h1_and_rewrite_from_one_parse(self) -> None:
        doc = parse("# Title\n\nsee [x](a.md)\n")
        assert first_h1(doc) == "Title"
        assert rewrite_inline_links(doc, _resolve) == "# Title\n\nsee [x](A)\n"
