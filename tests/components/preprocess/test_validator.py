"""Tests for validator — Validator class, parse_yaml."""

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from another_mood.components.preprocess.position_resolver import Position
from another_mood.components.preprocess.validator import (
    Location,
    UserStr,
    Validator,
    parse_yaml,
)
from another_mood.components.shared.diagnostic import FileValidationError

_DUMMY_FILE = Path("test.yaml")
_ruamel = YAML()


def _ruamel_load(src: str) -> Any:
    return _ruamel.load(src)  # type: ignore[no-untyped-call]


# ── Validator.validate ──────────────────────────────────────────────


class TestValidate:
    """Validator.validate: Diagnostic conversion, position resolution."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = Validator(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            }
        )

    def test_ruamel_data_has_position(self) -> None:
        data = _ruamel_load("name: 42\n")
        errors = self.validator.validate(data, _DUMMY_FILE)
        assert len(errors) >= 1
        assert errors[0].line == 1
        assert errors[0].column is not None
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_plain_dict_has_no_position(self) -> None:
        data = {"name": 42}
        errors = self.validator.validate(data, _DUMMY_FILE)
        assert len(errors) >= 1
        assert errors[0].line is None
        assert errors[0].column is None

    def test_valid_data_returns_empty(self) -> None:
        data = _ruamel_load("name: Alice\nage: 30\n")
        assert self.validator.validate(data, _DUMMY_FILE) == []

    def test_non_mapping(self) -> None:
        data = [{"just": "a list"}]
        errors = self.validator.validate(data, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].source == "jsonschema"


# ── identifier-aware position resolution ────────────────────────────


class TestQuotedIdentifierPosition:
    """Diagnostics point at the quoted identifier in the error message
    when that identifier exists in the YAML; otherwise fall back to the
    parent location of the failing path."""

    def test_unexpected_property_points_at_the_offending_key(self) -> None:
        validator = Validator(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "additionalProperties": False,
            }
        )
        data = _ruamel_load(
            "name: Alice\n"  # line 1
            "extra: foo\n"  # line 2, col 1
        )
        errors = validator.validate(data, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].line == 2
        assert errors[0].column == 1

    def test_message_without_quoted_identifier_uses_path_position(self) -> None:
        # type errors do not quote an identifier; behaviour should be
        # identical to before — point at the failing value.
        validator = Validator(
            {
                "type": "object",
                "properties": {"age": {"type": "integer"}},
            }
        )
        data = _ruamel_load(
            "age: not-a-number\n"  # line 1, value at col 6
        )
        errors = validator.validate(data, _DUMMY_FILE)
        assert len(errors) == 1
        assert errors[0].line == 1
        assert errors[0].column == 6


# ── parse_yaml ─────────────────────────────────────────────────────


class TestParseYaml:
    """parse_yaml: YAML parsing with source position preservation."""

    def test_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.yaml"
        f.write_text("key: value\n")
        result = parse_yaml(f)
        assert result["key"] == "value"

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
        assert name.location == Location(file=f, position=Position(line=2, column=9))
        assert isinstance(tag, UserStr)
        assert tag.location == Location(file=f, position=Position(line=4, column=7))

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
    loc = Location(file=Path("foo.yaml"), position=Position(line=3, column=7))
    s = UserStr("hello", loc)
    assert s == "hello"
    assert s.location is loc
