"""Tests for validator — Validator class."""

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from another_mood.components.preprocess.validator import Validator

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
