"""Tests for validator — Validator class."""

from typing import Any

import pytest
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from another_mood.components.shared.user_source.validator import Validator

_ruamel = YAML()


def _ruamel_load(src: str) -> Any:
    return _ruamel.load(src)  # type: ignore[no-untyped-call]


# ── Validator.validate ──────────────────────────────────────────────


class TestValidate:
    """Validator.validate: ValidationIssue conversion, position resolution."""

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
        issues = self.validator.validate(data)
        assert len(issues) >= 1
        assert issues[0].line == 1
        assert issues[0].column is not None
        assert issues[0].source == "jsonschema"

    def test_plain_dict_has_no_position(self) -> None:
        data = {"name": 42}
        issues = self.validator.validate(data)
        assert len(issues) >= 1
        assert issues[0].line is None
        assert issues[0].column is None

    def test_valid_data_returns_empty(self) -> None:
        data = _ruamel_load("name: Alice\nage: 30\n")
        assert self.validator.validate(data) == []

    def test_non_mapping(self) -> None:
        data = [{"just": "a list"}]
        issues = self.validator.validate(data)
        assert len(issues) == 1
        assert issues[0].source == "jsonschema"


# ── identifier-aware position resolution ────────────────────────────


class TestQuotedIdentifierPosition:
    """Issues point at the quoted identifier in the error message
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
        issues = validator.validate(data)
        assert len(issues) == 1
        assert issues[0].line == 2
        assert issues[0].column == 1

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
        issues = validator.validate(data)
        assert len(issues) == 1
        assert issues[0].line == 1
        assert issues[0].column == 6


# ── anyOf / oneOf descent ───────────────────────────────────────────


class TestAnyOfSubviolation:
    """When validation fails inside an ``anyOf`` / ``oneOf`` branch, the
    issue should surface the deepest branch error rather than the
    top-level ``"... is not valid under any of the given schemas"``
    wrapper with its full instance dump."""

    def test_anyof_surfaces_deepest_subviolation(self) -> None:
        validator = Validator(
            {
                "type": "object",
                "properties": {
                    "value": {
                        "anyOf": [
                            {"type": "object", "required": ["kind"]},
                            {"const": False},
                        ]
                    }
                },
            }
        )
        data = _ruamel_load(
            "value:\n"  # line 1
            "  other: x\n"  # line 2
        )
        issues = validator.validate(data)
        assert len(issues) == 1
        assert "is not valid under any of the given schemas" not in issues[0].message
        assert issues[0].message == "'kind' is a required property"
        # Position points into the failing branch's path (the value mapping),
        # not the outer anyOf wrapper.
        assert issues[0].line is not None
