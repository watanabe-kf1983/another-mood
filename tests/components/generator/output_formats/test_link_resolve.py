"""Tests for the ``node:`` link-resolution transform, with a stand-in renderer."""

from another_mood.components.generator.output_formats.link_resolve import resolve_links

# A handful of known anchor paths map to URLs; everything else is unresolved.
_URLS = {
    "/roadmap": "../roadmap.md#/roadmap",
    "/prose/design/書籍": "x/book.md#/prose/design/書籍",
}


def _render_dest(anchor_path: str) -> str:
    """Stand-in for md.py's renderer: a resolved path becomes a ``(url)``
    destination, an unresolved one becomes empty — dropping the destination
    leaves the link text as a plain ``[text]``."""
    url = _URLS.get(anchor_path)
    return f"({url})" if url is not None else ""


class TestResolvedLink:
    """A known ``node:`` reference is replaced by the rendered link."""

    def test_splices_the_rendered_link(self) -> None:
        assert (
            resolve_links("see [doc](node:/roadmap) ok", _render_dest)
            == "see [doc](../roadmap.md#/roadmap) ok"
        )

    def test_resolves_an_iri_path_without_percent_encoding(self) -> None:
        # normalizeLink identity keeps the non-ASCII path raw, so it matches
        # both the source (to splice) and the IRI-form node-map key (to look up).
        assert (
            resolve_links("ref [本](node:/prose/design/書籍) end", _render_dest)
            == "ref [本](x/book.md#/prose/design/書籍) end"
        )

    def test_resolves_repeated_links_in_one_block(self) -> None:
        assert resolve_links(
            "[a](node:/roadmap) then [b](node:/roadmap)", _render_dest
        ) == ("[a](../roadmap.md#/roadmap) then [b](../roadmap.md#/roadmap)")

    def test_resolves_a_link_split_across_lines(self) -> None:
        assert resolve_links("para [link\ntext](node:/roadmap) x", _render_dest) == (
            "para [link\ntext](../roadmap.md#/roadmap) x"
        )


class TestUnresolvedLink:
    """An unknown ``node:`` reference drops its destination, leaving the link
    text as a plain, conspicuous ``[text]``."""

    def test_drops_the_destination_keeping_bracketed_text(self) -> None:
        assert resolve_links("see [the doc](node:/missing) ok", _render_dest) == (
            "see [the doc] ok"
        )


class TestScopeAndImmunity:
    """Only real links are touched; non-links and other schemes are left alone."""

    def test_leaves_a_fenced_code_example_untouched(self) -> None:
        # The fence is a separate block with no link_open, and the real link
        # after it still resolves.
        assert resolve_links(
            "```\n[c](node:/roadmap)\n```\n[d](node:/roadmap)", _render_dest
        ) == ("```\n[c](node:/roadmap)\n```\n[d](../roadmap.md#/roadmap)")

    def test_leaves_an_inline_code_node_example_untouched(self) -> None:
        # `node:/x` inside a code span carries no `](…)`, so nothing matches it.
        assert resolve_links(
            "the `node:/roadmap` scheme and [d](node:/roadmap)", _render_dest
        ) == ("the `node:/roadmap` scheme and [d](../roadmap.md#/roadmap)")

    def test_ignores_a_non_node_scheme(self) -> None:
        assert resolve_links("[r](../y.md) and [d](node:/roadmap)", _render_dest) == (
            "[r](../y.md) and [d](../roadmap.md#/roadmap)"
        )

    def test_resolves_a_link_inside_a_list_item(self) -> None:
        # Unlike under_heading, relink touches links anywhere, not just at the
        # outline's top level.
        assert resolve_links("- item [d](node:/roadmap)\n- two", _render_dest) == (
            "- item [d](../roadmap.md#/roadmap)\n- two"
        )


class TestNonGoalFormsLeftVerbatim:
    """Reference-style and autolink ``node:`` forms are non-goals: their
    ``](href)`` is not in the source, so they are left untouched, not crashed."""

    def test_reference_style_link_is_left_as_is(self) -> None:
        src = "see [doc][r]\n\n[r]: node:/roadmap\n"
        assert resolve_links(src, _render_dest) == src

    def test_autolink_is_left_as_is(self) -> None:
        src = "see <node:/roadmap>\n"
        assert resolve_links(src, _render_dest) == src


class TestEdges:
    def test_empty_input_yields_empty(self) -> None:
        assert resolve_links("", _render_dest) == ""

    def test_body_with_no_node_links_is_unchanged(self) -> None:
        body = "# Title\n\nA paragraph, a [real](../x.md) link, and prose.\n"
        assert resolve_links(body, _render_dest) == body
