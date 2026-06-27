"""Tests for prose preprocessing — derive_prose_titles."""

from another_mood.components.preprocess.prose import derive_prose_titles


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


class TestDeriveProseTitles:
    """derive_prose_titles: add a Markdown-derived ``title`` to prose records."""

    def test_h1_at_beginning(self) -> None:
        result = derive_prose_titles(_prose("# Title\n\nBody.\n\n## Section\n"))
        assert _record(result)["title"] == "Title"

    def test_h1_at_end(self) -> None:
        result = derive_prose_titles(_prose("Some intro text.\n\n# Late Title\n"))
        assert _record(result)["title"] == "Late Title"

    def test_two_h1s_uses_first(self) -> None:
        result = derive_prose_titles(_prose("# First\n\nText.\n\n# Second\n"))
        assert _record(result)["title"] == "First"

    def test_no_h1_leaves_title_absent(self) -> None:
        result = derive_prose_titles(_prose("Just plain text.\n"))
        assert "title" not in _record(result)

    def test_h2_is_not_a_title(self) -> None:
        result = derive_prose_titles(_prose("## Not a title\n\nContent.\n"))
        assert "title" not in _record(result)

    def test_id_and_body_preserved(self) -> None:
        result = derive_prose_titles(_prose("# Hello\n\nContent.\n"))
        record = _record(result)
        assert record["id"] == "doc"
        assert record["body"] == {
            "mime_type": "text/markdown",
            "content": "# Hello\n\nContent.\n",
        }

    def test_existing_title_is_not_overwritten(self) -> None:
        result = derive_prose_titles(_prose("# H1 Title\n", title="Explicit"))
        assert _record(result)["title"] == "Explicit"

    def test_existing_non_string_title_is_preserved(self) -> None:
        # Any ``title`` key counts as already-titled and is left untouched,
        # regardless of its value type — never overwritten by the H1.
        result = derive_prose_titles(_prose("# H1 Title\n", title=123))
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
        assert "title" not in _record(derive_prose_titles(data))

    def test_non_prose_data_passes_through(self) -> None:
        data = {"items": [{"id": "a", "name": "A"}]}
        assert derive_prose_titles(data) == data
