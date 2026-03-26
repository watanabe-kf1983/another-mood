"""Tests for prose — Markdown to JSON data model conversion."""

from reqs_builder.prose import parse_markdown


class TestParseMarkdown:
    """parse_markdown: (markdown_str, id) -> dict"""

    def test_basic(self) -> None:
        md = "# Hello\n\nSome content.\n"
        result = parse_markdown(md, "background")
        assert result == {
            "id": "background",
            "title": "Hello",
            "body": {
                "_mime_type": "text/markdown",
                "_content": "# Hello\n\nSome content.\n",
            },
        }

    def test_no_h1(self) -> None:
        md = "Just plain text.\n"
        result = parse_markdown(md, "notes")
        assert result == {
            "id": "notes",
            "title": None,
            "body": {
                "_mime_type": "text/markdown",
                "_content": "Just plain text.\n",
            },
        }

    def test_h1_at_beginning(self) -> None:
        md = "# Title\n\nBody text.\n\n## Section\n\nMore text.\n"
        result = parse_markdown(md, "doc")
        assert result["title"] == "Title"

    def test_h1_at_end(self) -> None:
        md = "Some intro text.\n\n# Late Title\n"
        result = parse_markdown(md, "doc")
        assert result["title"] == "Late Title"

    def test_two_h1s_uses_first(self) -> None:
        md = "# First\n\nText.\n\n# Second\n"
        result = parse_markdown(md, "doc")
        assert result["title"] == "First"

    def test_body_is_full_content(self) -> None:
        md = "# Title\n\nParagraph.\n"
        result = parse_markdown(md, "doc")
        assert result["body"]["_content"] == md

    def test_h2_is_not_title(self) -> None:
        md = "## Not a title\n\nContent.\n"
        result = parse_markdown(md, "doc")
        assert result["title"] is None

    def test_id_passed_through(self) -> None:
        md = "# Whatever\n"
        result = parse_markdown(md, "guides/ordering")
        assert result["id"] == "guides/ordering"
