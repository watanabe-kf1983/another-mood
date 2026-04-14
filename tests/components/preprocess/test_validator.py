"""Tests for validator — Validator class, parse_yaml."""

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML  # type: ignore[attr-defined]

from another_mood.components.preprocess.validator import Validator, parse_yaml
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
