"""Tests for JSON data model — deep merge and YAML loading."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from another_mood.components.shared.json_data_model import (
    collect_files,
    deep_merge,
    load_model,
    save_model,
)


class TestDeepMerge:
    def test_disjoint_keys(self) -> None:
        result = deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_objects_merged_recursively(self) -> None:
        base: dict[str, Any] = {"config": {"database": {"host": "localhost"}}}
        override: dict[str, Any] = {"config": {"database": {"port": 5432}}}

        result = deep_merge(base, override)
        assert result == {"config": {"database": {"host": "localhost", "port": 5432}}}

    def test_arrays_concatenated(self) -> None:
        base: dict[str, Any] = {"entities": [{"id": "user"}]}
        override: dict[str, Any] = {"entities": [{"id": "order"}]}

        result = deep_merge(base, override)
        assert result == {"entities": [{"id": "user"}, {"id": "order"}]}

    def test_scalars_later_wins(self) -> None:
        base: dict[str, Any] = {"config": {"database": {"host": "localhost"}}}
        override: dict[str, Any] = {"config": {"database": {"host": "production"}}}

        result = deep_merge(base, override)
        assert result == {"config": {"database": {"host": "production"}}}

    def test_empty_base(self) -> None:
        result = deep_merge({}, {"key": "value"})
        assert result == {"key": "value"}

    def test_empty_override(self) -> None:
        result = deep_merge({"key": "value"}, {})
        assert result == {"key": "value"}

    def test_both_empty(self) -> None:
        result = deep_merge({}, {})
        assert result == {}

    def test_does_not_mutate_inputs(self) -> None:
        base: dict[str, Any] = {"items": [1], "config": {"a": 1}}
        override: dict[str, Any] = {"items": [2], "config": {"b": 2}}
        base_copy: dict[str, Any] = {"items": [1], "config": {"a": 1}}
        override_copy: dict[str, Any] = {"items": [2], "config": {"b": 2}}

        deep_merge(base, override)
        assert base == base_copy
        assert override == override_copy


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestCollectFiles:
    """collect_files: expand path arguments into a list of files (order unspecified)."""

    def test_no_args_returns_empty(self) -> None:
        assert collect_files() == []

    def test_file_path_included(self, tmp_path: Path) -> None:
        f = tmp_path / "schema.yaml"
        f.write_text("a: 1")

        assert collect_files(f) == [f]

    def test_directory_recursively_scanned(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        a = d / "a.yaml"
        b = d / "sub" / "b.yaml"
        _write_yaml(a, {"a": 1})
        _write_yaml(b, {"b": 2})

        assert set(collect_files(d)) == {a, b}

    def test_missing_path_skipped(self, tmp_path: Path) -> None:
        present = tmp_path / "schema.yaml"
        present.write_text("a: 1")
        missing = tmp_path / "missing.yaml"

        assert collect_files(present, missing) == [present]

    def test_files_and_dirs_combined(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        in_dir = d / "in_dir.yaml"
        _write_yaml(in_dir, {"a": 1})
        f = tmp_path / "alone.yaml"
        _write_yaml(f, {"b": 2})

        assert set(collect_files(d, f)) == {in_dir, f}


class TestLoadModel:
    """load_model: read each YAML mapping and deep-merge them into a single dict."""

    def test_no_paths_returns_empty(self) -> None:
        assert load_model() == {}

    def test_loads_and_merges_yaml_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "builtin.yaml"
        f2 = tmp_path / "user.yaml"
        _write_yaml(f1, {"properties": {"prose": {"type": "array"}}})
        _write_yaml(f2, {"properties": {"users": {"type": "object"}}})

        assert load_model(f1, f2) == {
            "properties": {
                "prose": {"type": "array"},
                "users": {"type": "object"},
            }
        }

    def test_non_yaml_files_ignored(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        _write_yaml(d / "data.yaml", {"key": "value"})
        (d / "readme.md").write_text("# md")

        assert load_model(d) == {"key": "value"}

    def test_non_mapping_yaml_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n")

        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            load_model(f)


class TestSaveModel:
    """save_model: write a YAML 1.2 file with project serialization conventions."""

    def test_multiline_string_uses_literal_block(self, tmp_path: Path) -> None:
        out = tmp_path / "out.yaml"
        save_model(out, {"body": "line1\nline2\n"})
        text = out.read_text()
        assert "|\n" in text
        assert yaml.safe_load(text)["body"] == "line1\nline2\n"

    def test_single_line_string_not_block(self, tmp_path: Path) -> None:
        out = tmp_path / "out.yaml"
        save_model(out, {"title": "Hello"})
        assert "|\n" not in out.read_text()

    def test_no_yaml_directive(self, tmp_path: Path) -> None:
        # YAML 1.2 is ruamel.yaml's default; emitting a %YAML directive is
        # unnecessary and would just clutter pipeline-internal files.
        out = tmp_path / "out.yaml"
        save_model(out, {"x": 1})
        assert "%YAML" not in out.read_text()

    def test_drops_none_keys_recursively(self, tmp_path: Path) -> None:
        out = tmp_path / "out.yaml"
        save_model(out, {"keep": 1, "drop": None, "nested": {"keep": 2, "drop": None}})
        assert yaml.safe_load(out.read_text()) == {
            "keep": 1,
            "nested": {"keep": 2},
        }
