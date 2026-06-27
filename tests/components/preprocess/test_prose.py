"""Tests for prose preprocessing — preprocess_prose, normalize_links."""

from another_mood.components.preprocess.prose import (
    normalize_links,
    preprocess_prose,
)


def _prose(content: str, **extra: object) -> dict[str, object]:
    """Build loader-shaped prose data: one Markdown record under ``prose``."""
    record: dict[str, object] = {
        "id": "doc",
        "body": {"mime_type": "text/markdown", "content": content},
        **extra,
    }
    return {"prose": [record]}


def _record(data: object) -> dict[str, object]:
    return data["prose"][0]  # type: ignore[index, return-value]


class TestPreprocessProseTitle:
    """preprocess_prose: derive a Markdown ``title`` from the first H1."""

    def test_h1_at_beginning(self) -> None:
        result = preprocess_prose(_prose("# Title\n\nBody.\n\n## Section\n"))
        assert _record(result)["title"] == "Title"

    def test_h1_at_end(self) -> None:
        result = preprocess_prose(_prose("Some intro text.\n\n# Late Title\n"))
        assert _record(result)["title"] == "Late Title"

    def test_two_h1s_uses_first(self) -> None:
        result = preprocess_prose(_prose("# First\n\nText.\n\n# Second\n"))
        assert _record(result)["title"] == "First"

    def test_no_h1_leaves_title_absent(self) -> None:
        result = preprocess_prose(_prose("Just plain text.\n"))
        assert "title" not in _record(result)

    def test_h2_is_not_a_title(self) -> None:
        result = preprocess_prose(_prose("## Not a title\n\nContent.\n"))
        assert "title" not in _record(result)

    def test_existing_title_is_not_overwritten(self) -> None:
        result = preprocess_prose(_prose("# H1 Title\n", title="Explicit"))
        assert _record(result)["title"] == "Explicit"

    def test_existing_non_string_title_is_preserved(self) -> None:
        # Any ``title`` key counts as already-titled and is left untouched,
        # regardless of its value type — never overwritten by the H1.
        result = preprocess_prose(_prose("# H1 Title\n", title=123))
        assert _record(result)["title"] == 123

    def test_non_markdown_body_is_skipped(self) -> None:
        data = {
            "prose": [
                {
                    "id": "doc",
                    "body": {"mime_type": "text/plain", "content": "# Not parsed\n"},
                }
            ]
        }
        assert "title" not in _record(preprocess_prose(data))

    def test_non_prose_data_passes_through(self) -> None:
        data = {"items": [{"id": "a", "name": "A"}]}
        assert preprocess_prose(data) == data


class TestPreprocessProseLinks:
    """preprocess_prose: rewrite relative links in each Markdown prose body."""

    def test_rewrites_body_content(self) -> None:
        result = preprocess_prose(_prose("see [t](other.md)\n", id="a/b/doc"))
        assert _record(result)["body"] == {
            "mime_type": "text/markdown",
            "content": "see [t](node:/prose/a/b/other)\n",
        }

    def test_title_and_links_from_one_pass(self) -> None:
        # The single parse derives both: H1 title and a normalized link.
        result = preprocess_prose(_prose("# Doc\n\nsee [t](other.md)\n", id="a/b/doc"))
        record = _record(result)
        assert record["title"] == "Doc"
        assert record["body"]["content"] == "# Doc\n\nsee [t](node:/prose/a/b/other)\n"  # type: ignore[index]

    def test_body_without_links_is_returned_unchanged(self) -> None:
        # No H1 (no title to add) and no links: the record passes through as-is.
        data = _prose("Plain prose, no links.\n", id="a/b/doc")
        assert preprocess_prose(data) == data

    def test_non_markdown_body_keeps_links_verbatim(self) -> None:
        data = {
            "prose": [
                {
                    "id": "a/b/doc",
                    "body": {"mime_type": "text/plain", "content": "[t](x.md)"},
                }
            ]
        }
        assert preprocess_prose(data) == data


# The referencing document for the pure-function tests; ``base`` is "a/b".
_DOC = "a/b/doc"


class TestNormalizeLinksConverted:
    """Relative ``.md`` links resolving inside contents become ``node:`` refs."""

    def test_sibling_md_link(self) -> None:
        assert normalize_links("see [t](other.md) ok", _DOC) == (
            "see [t](node:/prose/a/b/other) ok"
        )

    def test_parent_dir_link(self) -> None:
        assert normalize_links("[t](../c/x.md)", _DOC) == "[t](node:/prose/a/c/x)"

    def test_dot_segment_is_collapsed(self) -> None:
        assert normalize_links("[t](./sub/x.md)", _DOC) == (
            "[t](node:/prose/a/b/sub/x)"
        )

    def test_path_fragment_is_dropped(self) -> None:
        # A5 drops the #fragment (A7 will carry it through); the page resolves.
        assert normalize_links("[t](x.md#sec)", _DOC) == "[t](node:/prose/a/b/x)"

    def test_self_reference_by_filename(self) -> None:
        assert normalize_links("[t](doc.md)", _DOC) == "[t](node:/prose/a/b/doc)"

    def test_top_level_document_has_empty_base(self) -> None:
        assert normalize_links("[t](sub/x.md)", "index") == "[t](node:/prose/sub/x)"

    def test_cjk_path_is_kept_raw(self) -> None:
        # normalizeLink identity keeps the non-ASCII path raw on both sides.
        assert normalize_links("[本](書籍.md)", _DOC) == "[本](node:/prose/a/b/書籍)"

    def test_uppercase_extension(self) -> None:
        assert normalize_links("[t](X.MD)", _DOC) == "[t](node:/prose/a/b/X)"

    def test_repeated_links_in_one_block(self) -> None:
        assert normalize_links("[a](x.md) and [b](y.md)", _DOC) == (
            "[a](node:/prose/a/b/x) and [b](node:/prose/a/b/y)"
        )

    def test_link_split_across_lines(self) -> None:
        assert normalize_links("para [link\ntext](x.md) z", _DOC) == (
            "para [link\ntext](node:/prose/a/b/x) z"
        )

    def test_link_inside_a_list_item(self) -> None:
        assert normalize_links("- item [t](x.md)\n- two", _DOC) == (
            "- item [t](node:/prose/a/b/x)\n- two"
        )


class TestNormalizeLinksVerbatim:
    """Links that don't name an in-tree prose document are left byte-for-byte."""

    def test_pure_fragment_is_same_page(self) -> None:
        assert normalize_links("[t](#sec)", _DOC) == "[t](#sec)"

    def test_escape_outside_contents(self) -> None:
        assert normalize_links("[t](../../../docs/x.md)", _DOC) == (
            "[t](../../../docs/x.md)"
        )

    def test_absolute_path(self) -> None:
        assert normalize_links("[t](/abs/x.md)", _DOC) == "[t](/abs/x.md)"

    def test_http_scheme(self) -> None:
        src = "[t](https://example.com/x.md)"
        assert normalize_links(src, _DOC) == src

    def test_node_scheme_already_canonical(self) -> None:
        assert normalize_links("[t](node:/prose/x)", _DOC) == "[t](node:/prose/x)"

    def test_mailto_scheme(self) -> None:
        assert normalize_links("[t](mailto:a@b.com)", _DOC) == "[t](mailto:a@b.com)"

    def test_non_markdown_target(self) -> None:
        assert normalize_links("![alt](img.png)", _DOC) == "![alt](img.png)"

    def test_fenced_code_example_is_untouched(self) -> None:
        # The fence is a separate block with no link_open; the real link after
        # it still resolves.
        assert normalize_links("```\n[c](fenced.md)\n```\n[d](real.md)", _DOC) == (
            "```\n[c](fenced.md)\n```\n[d](node:/prose/a/b/real)"
        )

    def test_inline_code_is_untouched(self) -> None:
        # `x.md` in a code span carries no `](…)`, so nothing matches it.
        assert normalize_links("the `x.md` file and [d](real.md)", _DOC) == (
            "the `x.md` file and [d](node:/prose/a/b/real)"
        )

    def test_reference_style_link_is_left_as_is(self) -> None:
        src = "see [t][r]\n\n[r]: other.md\n"
        assert normalize_links(src, _DOC) == src

    def test_empty_input(self) -> None:
        assert normalize_links("", _DOC) == ""
