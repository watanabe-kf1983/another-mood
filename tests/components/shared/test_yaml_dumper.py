"""Tests for yaml_dumper — shared YAML serialization."""

from io import StringIO

import yaml

from reqs_builder.components.shared import yaml_dumper


def _dump_to_str(data: object) -> str:
    buf = StringIO()
    yaml_dumper.dump(data, buf)
    return buf.getvalue()


class TestDump:
    def test_multiline_string_uses_literal_block(self) -> None:
        result = _dump_to_str({"body": "line1\nline2\n"})
        assert "|\n" in result
        assert yaml.safe_load(result)["body"] == "line1\nline2\n"

    def test_single_line_string_not_block(self) -> None:
        result = _dump_to_str({"title": "Hello"})
        assert "|\n" not in result

    def test_yaml_11_directive(self) -> None:
        result = _dump_to_str({"x": 1})
        assert "%YAML 1.1" in result
