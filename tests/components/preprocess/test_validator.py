"""Tests for validator — validate_data, parse_yaml, and content validator."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from reqs_builder.components.preprocess.validator import (
    build_content_validator,
    parse_yaml,
    validate_data,
)
from reqs_builder.components.shared.diagnostic import FileValidationError

_DUMMY_FILE = Path("test.yaml")
_ruamel = YAML()


def _ruamel_load(src: str) -> Any:
    return _ruamel.load(src)  # type: ignore[no-untyped-call]


# ── validate_data ───────────────────────────────────────────────────

# Use a simple schema for testing validate_data independently.
_SIMPLE_VALIDATOR = build_content_validator(
    yaml.safe_load("""
        name: { type: string }
        age: { type: integer }
    """)
)


class TestValidateData:
    """Core validation: Diagnostic conversion, position resolution."""

    def test_ruamel_data_has_position(self) -> None:
        data = _ruamel_load("name: 42\n")
        errors = validate_data(data, _DUMMY_FILE, _SIMPLE_VALIDATOR)
        assert len(errors) >= 1
        assert errors[0].line == 1
        assert errors[0].column is not None
        assert errors[0].file == _DUMMY_FILE
        assert errors[0].source == "jsonschema"

    def test_plain_dict_has_no_position(self) -> None:
        data = {"name": 42}
        errors = validate_data(data, _DUMMY_FILE, _SIMPLE_VALIDATOR)
        assert len(errors) >= 1
        assert errors[0].line is None
        assert errors[0].column is None

    def test_valid_data_returns_empty(self) -> None:
        data = _ruamel_load("name: Alice\nage: 30\n")
        assert validate_data(data, _DUMMY_FILE, _SIMPLE_VALIDATOR) == []

    def test_non_mapping(self) -> None:
        data = [{"just": "a list"}]
        errors = validate_data(data, _DUMMY_FILE, _SIMPLE_VALIDATOR)
        assert len(errors) == 1
        assert errors[0].source == "jsonschema"


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


# ── build_content_validator ─────────────────────────────────────────


class TestBuildContentValidator:
    _validator = build_content_validator(
        yaml.safe_load("""
            items:
              type: array
              items:
                type: object
                properties:
                  id: { type: string }
                  name: { type: string }
                required: [id, name]
        """)
    )

    def test_valid(self) -> None:
        data = yaml.safe_load("items:\n  - id: a\n    name: Alice\n")
        assert validate_data(data, _DUMMY_FILE, self._validator) == []

    def test_invalid(self) -> None:
        data = yaml.safe_load("items:\n  - id: a\n")  # missing 'name'
        errors = validate_data(data, _DUMMY_FILE, self._validator)
        assert len(errors) >= 1
        assert "name" in errors[0].message
