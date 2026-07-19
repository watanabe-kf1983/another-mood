"""Tests for the shared Markdown module — parse, first_h1, rewrite_inline_links.

These cover each operation's own contract over a parsed body: the H1 lookup,
the resolve trichotomy (retarget / drop / decline), in-order splicing, and what
is structurally out of scope (code, non-bare destinations).  Caller-specific
scenarios live with each caller's tests (e.g. the ``node:`` policy in
``test_md.py``'s relink wiring, the relative-link policy in ``test_prose.py``)."""

import pytest

from another_mood.components.shared.markdown import (
    first_h1,
    github_slug,
    heading_nodes,
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


class TestGithubSlug:
    r"""github_slug: GitHub's de-facto heading-anchor slug (\p{Word} rule).

    The core cases (ASCII, CJK, punctuation) are where GitHub, Hugo, and VS Code
    coincide; they also match real Hugo output for this project's prose. The
    ``\p{Word}`` edge case follows GitHub, which is the target renderer-agnostic
    slug, not Hugo's own ``autoid.go``."""

    # (heading text, expected slug) — the shared core, then the \p{Word} edge.
    @pytest.mark.parametrize(
        ("text", "slug"),
        [
            ("Anchor Specification", "anchor-specification"),  # lowercase, space→-
            ("ID 体系", "id-体系"),  # ASCII lowercased, CJK kept
            ("Escape 規則", "escape-規則"),
            ("mood_view 自動アンカー刻印", "mood_view-自動アンカー刻印"),  # _ kept
            ("API の設計", "api-の設計"),
            ("用語", "用語"),  # CJK only, unchanged
            ("藤岡弘、", "藤岡弘"),  # CJK punctuation dropped
            ("モーニング娘。", "モーニング娘"),
            ("Version 1.0", "version-10"),  # decimal kept, '.' dropped
            # \p{Word} keeps letter-numbers (Ⅷ, Nl) but not other numerics
            # (①, No). Hugo drops both; we follow GitHub, not our renderer.
            ("第①章Ⅷ巻", "第章ⅷ巻"),
        ],
    )
    def test_matches_github(self, text: str, slug: str) -> None:
        assert github_slug(text) == slug

    def test_runs_are_not_collapsed(self) -> None:
        # A space and a dropped symbol each keep their own separator, matching
        # GitHub's straight per-character mapping (no run collapsing).
        assert github_slug("a  b") == "a--b"
        assert github_slug("foo & bar") == "foo--bar"

    def test_hyphen_is_kept(self) -> None:
        assert github_slug("a-b") == "a-b"

    def test_empty(self) -> None:
        assert github_slug("") == ""


class TestHeadingNodes:
    """heading_nodes: the body's headings as ``{id, title, level}`` link targets."""

    def test_extracts_in_document_order_with_levels(self) -> None:
        doc = parse("# Top\n\n## エラー処理\n\n### API の設計\n")
        assert heading_nodes(doc) == [
            {"id": "top", "title": "Top", "level": 1},
            {"id": "エラー処理", "title": "エラー処理", "level": 2},
            {"id": "api-の設計", "title": "API の設計", "level": 3},
        ]

    def test_h1_is_included(self) -> None:
        # All levels are kept; the H1 (the prose title) is a link target too.
        assert heading_nodes(parse("# Only H1\n"))[0]["level"] == 1

    def test_no_headings_is_empty(self) -> None:
        assert heading_nodes(parse("Just prose, no headings.\n")) == []

    def test_slug_reads_visible_text_not_raw_markup(self) -> None:
        # A code span contributes its content, emphasis / link only inner text —
        # so the slug matches what the renderer sees, while the title keeps the
        # raw heading source.
        [code] = heading_nodes(parse("## prose body `relink`\n"))
        assert code == {
            "id": "prose-body-relink",
            "title": "prose body `relink`",
            "level": 2,
        }
        [link] = heading_nodes(parse("## See [docs](x.md)\n"))
        assert link == {"id": "see-docs", "title": "See [docs](x.md)", "level": 2}

    def test_duplicate_text_is_deduplicated(self) -> None:
        # Repeated text collides; each later one gets the lowest free -N suffix.
        ids = [h["id"] for h in heading_nodes(parse("## 背景\n\n## 背景\n\n## 背景\n"))]
        assert ids == ["背景", "背景-1", "背景-2"]

    def test_all_levels(self) -> None:
        src = "".join(f"{'#' * n} H{n}\n\n" for n in range(1, 7))
        assert [h["level"] for h in heading_nodes(parse(src))] == [1, 2, 3, 4, 5, 6]


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

    def test_retargets_an_image_destination(self) -> None:
        # An image shares the ``](dest)`` shape, so its src is rewritten while
        # the ``![alt]`` stays put.
        assert rewrite_inline_links(parse("see ![alt](a.md) ok"), _resolve) == (
            "see ![alt](A) ok"
        )

    def test_drops_an_image_destination_to_bare_alt(self) -> None:
        assert rewrite_inline_links(parse("see ![alt](gone) ok"), _resolve) == (
            "see ![alt] ok"
        )

    def test_rewrites_links_and_images_together_in_order(self) -> None:
        assert (
            rewrite_inline_links(parse("[x](a.md) ![y](gone) [z](keep.md)"), _resolve)
            == "[x](A) ![y] [z](keep.md)"
        )


class TestParseSharedAcrossOperations:
    """One parse feeds both operations — the path a multi-derivation caller uses."""

    def test_first_h1_and_rewrite_from_one_parse(self) -> None:
        doc = parse("# Title\n\nsee [x](a.md)\n")
        assert first_h1(doc) == "Title"
        assert rewrite_inline_links(doc, _resolve) == "# Title\n\nsee [x](A)\n"
