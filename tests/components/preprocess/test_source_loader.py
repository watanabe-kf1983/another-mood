"""Tests for source_loader — parse_yaml, parse_markdown, UserStr/Location."""

from pathlib import Path

import pytest

from another_mood.components.preprocess.source_loader import (
    Location,
    ProseRecord,
    UserStr,
    parse_markdown,
    parse_yaml,
)
from another_mood.components.shared.diagnostic import FileValidationError


# ── parse_yaml ─────────────────────────────────────────────────────


class TestParseYaml:
    """parse_yaml: YAML parsing with source position preservation."""

    def test_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.yaml"
        f.write_text("key: value\n")
        result = parse_yaml(f)
        assert result["key"] == "value"

    def test_empty_file_returns_empty_mapping(self, tmp_path: Path) -> None:
        # ruamel returns None for empty input; parse_yaml normalises that
        # to {} so callers can keep using the documented Mapping shape.
        f = tmp_path / "empty.yaml"
        f.write_text("")
        assert parse_yaml(f) == {}

    def test_whitespace_only_file_returns_empty_mapping(self, tmp_path: Path) -> None:
        f = tmp_path / "ws.yaml"
        f.write_text("\n  \n")
        assert parse_yaml(f) == {}

    @pytest.mark.parametrize(
        ("source", "expected_type"),
        [
            ("- a\n- b\n", "CommentedSeq"),
            ("42\n", "int"),
            ('"just a string"\n', "str"),
            ("true\n", "bool"),
        ],
    )
    def test_non_mapping_root_rejected(
        self, source: str, expected_type: str, tmp_path: Path
    ) -> None:
        f = tmp_path / "non_mapping.yaml"
        f.write_text(source)
        with pytest.raises(FileValidationError) as exc_info:
            parse_yaml(f)
        diag = exc_info.value.diagnostics[0]
        assert diag.file == f
        assert "Expected a YAML mapping" in diag.message
        assert expected_type in diag.message

    def test_broken_yaml_raises_diagnostic(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.yaml"
        f.write_text("a: [unterminated\n")
        with pytest.raises(FileValidationError) as exc_info:
            parse_yaml(f)
        diag = exc_info.value.diagnostics[0]
        assert diag.file == f
        assert diag.source == "ruamel.yaml"

    def test_scalar_strings_become_user_str_with_location(self, tmp_path: Path) -> None:
        f = tmp_path / "tagged.yaml"
        f.write_text(
            "top:\n"  # line 1
            "  name: alice\n"  # line 2, value column 9
            "  tags:\n"  # line 3
            "    - red\n"  # line 4, value column 7
        )
        result = parse_yaml(f)
        name = result["top"]["name"]  # type: ignore[index]
        tag = result["top"]["tags"][0]  # type: ignore[index]
        assert isinstance(name, UserStr)
        assert name.location == Location(file=f, line=2, column=9)
        assert isinstance(tag, UserStr)
        assert tag.location == Location(file=f, line=4, column=7)

    def test_dict_keys_and_non_string_scalars_left_untouched(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "untouched.yaml"
        f.write_text("count: 3\nflag: true\n")
        result = parse_yaml(f)
        keys = list(result.keys())
        assert all(type(k) is str for k in keys)  # plain str, not UserStr
        assert result["count"] == 3
        assert result["flag"] is True


# ── UserStr / Location ─────────────────────────────────────────────


def test_user_str_carries_location_and_behaves_as_str() -> None:
    loc = Location(file=Path("foo.yaml"), line=3, column=7)
    s = UserStr("hello", loc)
    assert s == "hello"
    assert s.location is loc


# ── parse_markdown ────────────────────────────────────────────────


class TestParseMarkdown:
    """parse_markdown: (markdown_str, id) -> ProseRecord"""

    def test_basic(self) -> None:
        md = "# Hello\n\nSome content.\n"
        result = parse_markdown(md, "background")
        assert result.id == "background"
        assert result.title == "Hello"
        assert result.body == md
        assert result.mime_type == "text/markdown"

    def test_no_h1(self) -> None:
        md = "Just plain text.\n"
        result = parse_markdown(md, "notes")
        assert result.title is None
        assert result.body == md

    def test_h1_at_beginning(self) -> None:
        md = "# Title\n\nBody text.\n\n## Section\n\nMore text.\n"
        result = parse_markdown(md, "doc")
        assert result.title == "Title"

    def test_h1_at_end(self) -> None:
        md = "Some intro text.\n\n# Late Title\n"
        result = parse_markdown(md, "doc")
        assert result.title == "Late Title"

    def test_two_h1s_uses_first(self) -> None:
        md = "# First\n\nText.\n\n# Second\n"
        result = parse_markdown(md, "doc")
        assert result.title == "First"

    def test_h2_is_not_title(self) -> None:
        md = "## Not a title\n\nContent.\n"
        result = parse_markdown(md, "doc")
        assert result.title is None

    def test_id_passed_through(self) -> None:
        md = "# Whatever\n"
        result = parse_markdown(md, "guides/ordering")
        assert result.id == "guides/ordering"


class TestProseRecordToData:
    """ProseRecord.to_data() -> Mapping for JSON data model"""

    def test_with_title(self) -> None:
        md = "# Hello\n\nContent.\n"
        result = parse_markdown(md, "background")
        assert result.to_data() == {
            "id": "background",
            "title": "Hello",
            "body": {
                "mime_type": "text/markdown",
                "content": md,
            },
        }

    def test_without_title(self) -> None:
        md = "Just text.\n"
        result = parse_markdown(md, "notes")
        data = result.to_data()
        assert "title" not in data
        assert isinstance(result, ProseRecord)
