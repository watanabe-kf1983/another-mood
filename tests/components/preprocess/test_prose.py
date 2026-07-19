"""Tests for prose preprocessing — preprocess_prose, normalize_links."""

from another_mood.components.preprocess.prose import (
    normalize_links,
    preprocess_prose,
)


def _prose(
    content: str, *, mime_type: str = "text/markdown", **extra: object
) -> dict[str, object]:
    """Build loader-shaped prose data: one record under ``prose``."""
    record: dict[str, object] = {
        "id": "doc",
        "mime_type": mime_type,
        "content": content,
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

    def test_non_markdown_content_is_skipped(self) -> None:
        data = _prose("# Not parsed\n", mime_type="text/plain")
        assert "title" not in _record(preprocess_prose(data))

    def test_non_prose_data_passes_through(self) -> None:
        data = {"items": [{"id": "a", "name": "A"}]}
        assert preprocess_prose(data) == data


class TestPreprocessProseLinks:
    """preprocess_prose: rewrite relative links in each Markdown record's
    content."""

    def test_rewrites_content(self) -> None:
        result = preprocess_prose(_prose("see [t](other.md)\n", id="a/b/doc"))
        record = _record(result)
        assert record["content"] == "see [t](node:/prose/a/b/other)\n"
        assert record["mime_type"] == "text/markdown"

    def test_title_and_links_from_one_pass(self) -> None:
        # The single parse derives both: H1 title and a normalized link.
        result = preprocess_prose(_prose("# Doc\n\nsee [t](other.md)\n", id="a/b/doc"))
        record = _record(result)
        assert record["title"] == "Doc"
        assert record["content"] == "# Doc\n\nsee [t](node:/prose/a/b/other)\n"

    def test_content_without_links_kept_verbatim(self) -> None:
        # No links to rewrite: the content passes through untouched (the
        # record still gains its id-derived order_key / depth).
        record = _record(
            preprocess_prose(_prose("Plain prose, no links.\n", id="a/b/doc"))
        )
        assert record["content"] == "Plain prose, no links.\n"

    def test_non_markdown_content_gets_outline_but_kept_verbatim(self) -> None:
        # order_key / depth are id-derived, so non-Markdown content gets them
        # too; only the content (and its links) is left untouched.
        data = _prose("[t](x.md)", mime_type="text/plain", id="a/b/doc")
        record = _record(preprocess_prose(data))
        assert (record["order_key"], record["depth"]) == ("a/b/doc", 4)
        assert record["content"] == "[t](x.md)"
        assert record["mime_type"] == "text/plain"
        assert "title" not in record


class TestPreprocessProseHeadings:
    """preprocess_prose: collect the Markdown content's headings as link
    targets."""

    def test_headings_are_collected(self) -> None:
        result = preprocess_prose(_prose("# Title\n\n## エラー処理\n\n### 詳細\n"))
        assert _record(result)["headings"] == [
            {"id": "title", "title": "Title", "level": 1},
            {"id": "エラー処理", "title": "エラー処理", "level": 2},
            {"id": "詳細", "title": "詳細", "level": 3},
        ]

    def test_no_headings_is_an_empty_list(self) -> None:
        # The key is always present for Markdown content, empty when there are none.
        assert _record(preprocess_prose(_prose("Plain prose.\n")))["headings"] == []

    def test_non_markdown_content_has_no_headings(self) -> None:
        # Headings come from parsing Markdown, so non-Markdown content gets none —
        # like ``title``, the key is simply absent (order_key / depth still apply).
        data = _prose("## Not parsed\n", mime_type="text/plain")
        record = _record(preprocess_prose(data))
        assert "headings" not in record


# The referencing document for the pure-function tests; ``base`` is "a/b".
_DOC = "a/b/doc"


class TestNormalizeLinksConverted:
    """Relative ``.md`` links resolving inside contents become prose ``node:``
    refs."""

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

    def test_path_fragment_is_carried(self) -> None:
        # The #fragment (a heading slug) rides onto the node: form verbatim.
        assert normalize_links("[t](x.md#sec)", _DOC) == "[t](node:/prose/a/b/x#sec)"

    def test_cjk_fragment_is_kept_raw(self) -> None:
        # Like the path, the fragment is never encoded — it must match the
        # heading's rendered id byte-for-byte.
        assert normalize_links("[t](x.md#エラー処理)", _DOC) == (
            "[t](node:/prose/a/b/x#エラー処理)"
        )

    def test_empty_fragment_is_dropped(self) -> None:
        # A bare trailing `#` names no heading: only the page reference remains.
        assert normalize_links("[t](x.md#)", _DOC) == "[t](node:/prose/a/b/x)"

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


class TestNormalizeLinksBlob:
    """Relative non-``.md`` links resolving inside contents become blob
    ``node:`` refs — the path kept whole (extension and all), an opaque fragment
    riding along rather than resolved as a heading slug."""

    def test_image_becomes_blob_node(self) -> None:
        # The image src is rewritten to the blob node; the extension stays.
        assert normalize_links("![alt](cover.png)", _DOC) == (
            "![alt](node:/blob/a/b/cover.png)"
        )

    def test_plain_link_to_a_file_becomes_blob_node(self) -> None:
        assert normalize_links("[data](sheet.csv)", _DOC) == (
            "[data](node:/blob/a/b/sheet.csv)"
        )

    def test_parent_dir_blob(self) -> None:
        assert normalize_links("![c](../img/x.png)", _DOC) == (
            "![c](node:/blob/a/img/x.png)"
        )

    def test_opaque_fragment_is_carried(self) -> None:
        # A blob is opaque: its own anchor (a PDF's page) rides through verbatim.
        assert normalize_links("[p](doc.pdf#page=3)", _DOC) == (
            "[p](node:/blob/a/b/doc.pdf#page=3)"
        )

    def test_extensionless_file_is_still_a_blob(self) -> None:
        # No `.md`, so a blob keyed by its full path; downstream drops it if no
        # such blob exists.
        assert normalize_links("[t](LICENSE)", _DOC) == "[t](node:/blob/a/b/LICENSE)"


class TestNormalizeLinksVerbatim:
    """Links that don't name an in-tree file are left byte-for-byte."""

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

    def test_escaping_image_is_left(self) -> None:
        # A blob-shaped ref climbing out of contents bails out like any escape,
        # before it could be classified as a blob.
        assert normalize_links("![a](../../../x.png)", _DOC) == "![a](../../../x.png)"

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


def _outline(prose_id: str) -> tuple[object, object]:
    """The (order_key, depth) preprocess_prose derives for ``prose_id``."""
    record = _record(preprocess_prose(_prose("# Title\n", id=prose_id)))
    return record["order_key"], record["depth"]


class TestOutlinePosition:
    """preprocess_prose derives order_key / depth from the id's folder path."""

    def test_root_index(self) -> None:
        # The root index leads everything (empty key) at the top level.
        assert _outline("index") == ("", 1)

    def test_folder_index(self) -> None:
        # A folder's index maps to the folder path, one level below the root.
        assert _outline("design/index") == ("design/", 2)

    def test_nested_folder_index(self) -> None:
        assert _outline("design/generator/index") == ("design/generator/", 3)

    def test_top_level_file_is_deeper_than_root(self) -> None:
        assert _outline("design/architecture") == ("design/architecture", 3)

    def test_nested_file_is_one_deeper_than_its_folder_index(self) -> None:
        assert _outline("design/generator/anchor-spec") == (
            "design/generator/anchor-spec",
            4,
        )


# The real dev-docs prose ids (source files + per-folder index pages), in the
# folder pre-order that sorting by order_key must produce.
_EXPECTED_ORDER = [
    "index",
    "background/index",
    "background/another-mood-original",
    "background/product",
    "design/index",
    "design/app/index",
    "design/app/config-spec",
    "design/app/mcp-design",
    "design/app/meta-documentation",
    "design/app/project-structure",
    "design/app/system-dev-docs",
    "design/architecture",
    "design/composer/index",
    "design/composer/queries-spec",
    "design/generator/index",
    "design/generator/anchor-spec",
    "design/generator/generator",
    "design/generator/output-format-spec",
    "design/generator/paging-spec",
    "design/generator/template-spec",
    "design/json-data-model",
    "design/normalizer/index",
    "design/normalizer/markdown-parser-spec",
    "design/normalizer/normalizer",
    "design/normalizer/schema-spec",
    "design/pipeline",
    "dev/index",
    "dev/checks",
    "dev/environment",
    "dev/setup",
    "dev/style-guide",
]


class TestOrderKeySortsToFolderPreorder:
    """Sorting prose records by order_key yields folder pre-order — the sort
    the book-edition template performs downstream."""

    def test_orders_the_real_tree_regardless_of_input_order(self) -> None:
        # Reverse the input so the order comes from the key, not the sequence.
        keys = {i: str(_outline(i)[0]) for i in _EXPECTED_ORDER}
        assert sorted(reversed(_EXPECTED_ORDER), key=lambda i: keys[i]) == (
            _EXPECTED_ORDER
        )

    def test_each_folder_index_precedes_its_own_subtree(self) -> None:
        ordered = _EXPECTED_ORDER
        for idx, prose_id in enumerate(ordered):
            if prose_id.endswith("/index"):
                folder = prose_id.removesuffix("index")  # keeps trailing slash
                subtree = [c for c in ordered if c.startswith(folder) and c != prose_id]
                assert all(ordered.index(c) > idx for c in subtree), prose_id
