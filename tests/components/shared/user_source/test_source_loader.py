"""Tests for source_loader — parse_yaml, UserStr/Location."""

from pathlib import Path

import pytest

from another_mood.components.shared.user_source.source_loader import (
    Location,
    UserStr,
    parse_yaml,
)
from another_mood.components.shared.user_source.position_resolver import (
    Position,
    resolve_position,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


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

    def test_mapping_keys_become_user_str_with_location(self, tmp_path: Path) -> None:
        f = tmp_path / "keys.yaml"
        f.write_text(
            "top:\n"  # line 1, key column 1
            "  name: alice\n"  # line 2, key column 3
        )
        result = parse_yaml(f)
        (top,) = result.keys()
        (name,) = result["top"].keys()  # type: ignore[union-attr]
        assert isinstance(top, UserStr)
        assert top.location == Location(file=f, line=1, column=1)
        assert isinstance(name, UserStr)
        assert name.location == Location(file=f, line=2, column=3)

    def test_non_string_scalars_left_untouched(self, tmp_path: Path) -> None:
        f = tmp_path / "untouched.yaml"
        f.write_text("count: 3\nflag: true\n")
        result = parse_yaml(f)
        assert result["count"] == 3
        assert result["flag"] is True

    def test_key_tagging_preserves_lc_for_position_resolution(
        self, tmp_path: Path
    ) -> None:
        """Tagging keys must leave ruamel's ``.lc`` intact so schema-validation
        position resolution keeps working — including the root node's own
        position (which anchors errors about the document root) and non-string
        scalars, whose positions cannot ride on a ``UserStr``."""
        f = tmp_path / "positions.yaml"
        f.write_text("count: 3\nnested:\n  flag: true\n")
        result = parse_yaml(f)
        assert resolve_position([], result) == Position(line=1, column=1)
        assert resolve_position(["count"], result) == Position(line=1, column=8)
        assert resolve_position(["nested", "flag"], result) == Position(
            line=3, column=9
        )


# ── UserStr / Location ─────────────────────────────────────────────


def test_user_str_carries_location_and_behaves_as_str() -> None:
    loc = Location(file=Path("foo.yaml"), line=3, column=7)
    s = UserStr("hello", loc)
    assert s == "hello"
    assert s.location is loc
