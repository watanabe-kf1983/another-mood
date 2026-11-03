"""Tests for the paragraph-length check that ``make ci`` runs."""

from pathlib import Path

from scripts.check_paragraph_length import (
    LIMITS,
    documents,
    limit_for,
    overlong_paragraphs,
    paragraphs,
    visible_length,
)


def texts(source: str) -> tuple[str, ...]:
    return tuple(p.text for p in paragraphs(source))


def starts(source: str) -> tuple[int, ...]:
    return tuple(p.line for p in paragraphs(source))


class TestParagraphs:
    def test_a_blank_line_separates_paragraphs(self) -> None:
        assert texts("One.\n\nTwo.\n") == ("One.", "Two.")

    def test_wrapped_lines_are_one_paragraph(self) -> None:
        assert texts("One\ntwo.\n") == ("One two.",)

    def test_a_paragraph_is_reported_at_its_first_line(self) -> None:
        assert starts("# Title\n\nOne\ntwo.\n\n- item\n") == (3, 6)

    def test_each_list_item_is_a_paragraph(self) -> None:
        assert texts("- a\n- b\n1. c\n2) d\n") == ("a", "b", "c", "d")

    def test_a_nested_item_is_its_own_paragraph(self) -> None:
        assert texts("- a\n  - b\n") == ("a", "b")

    def test_an_item_continues_on_an_indented_line(self) -> None:
        assert texts("- a\n  continued\n") == ("a continued",)

    def test_an_item_closes_the_paragraph_before_it(self) -> None:
        assert texts("Lead-in:\n- a\n") == ("Lead-in:", "a")

    def test_headings_and_tables_are_skipped(self) -> None:
        assert texts("# H\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nText.\n") == ("Text.",)

    def test_a_heading_closes_the_paragraph_before_it(self) -> None:
        assert texts("One.\n## H\nTwo.\n") == ("One.", "Two.")

    def test_fenced_code_is_skipped_including_prose_inside(self) -> None:
        source = "Before.\n```md\n- not an item\n\nnot a paragraph\n```\nAfter.\n"
        assert texts(source) == ("Before.", "After.")

    def test_a_tilde_fence_is_a_fence_too(self) -> None:
        assert texts("~~~\ncode\n~~~\nAfter.\n") == ("After.",)


class TestVisibleLength:
    def test_counts_characters_not_bytes(self) -> None:
        assert visible_length("日本語") == 3

    def test_excludes_link_targets_but_keeps_link_text(self) -> None:
        assert visible_length("see [the docs](https://example.com/a/b) now") == len(
            "see [the docs] now"
        )

    def test_excludes_every_link_target(self) -> None:
        assert visible_length("[a](x) [b](y)") == len("[a] [b]")


class TestOverlong:
    def test_reports_only_paragraphs_over_the_limit(self) -> None:
        source = "x" * 10 + "\n\n" + "y" * 11 + "\n"
        assert [p.line for p in overlong_paragraphs(source, 10)] == [3]


class TestScope:
    def test_english_documents_get_the_english_limit(self) -> None:
        assert limit_for(Path("docs/reference/cli.md")) == LIMITS["en"]
        assert limit_for(Path("README.md")) == LIMITS["en"]

    def test_everything_else_gets_the_japanese_limit(self) -> None:
        assert limit_for(Path("DEVELOPMENT.md")) == LIMITS["ja"]
        assert limit_for(Path("dev-docs/contents/index.md")) == LIMITS["ja"]

    def test_a_path_merely_starting_with_docs_is_not_english(self) -> None:
        assert limit_for(Path("docs-notes/a.md")) == LIMITS["ja"]

    def test_walks_the_roots_only(self, tmp_path: Path) -> None:
        for relative in (
            "README.md",
            "docs/reference/cli.md",
            "dev-docs/contents/20-design/10-external/a.md",
            "src/other.md",
        ):
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / relative).write_text("", encoding="utf-8")

        assert documents(tmp_path) == (
            Path("README.md"),
            Path("docs/reference/cli.md"),
            Path("dev-docs/contents/20-design/10-external/a.md"),
        )
