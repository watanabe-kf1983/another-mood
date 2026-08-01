"""Tests for JSON data model — deep merge, JSON and YAML loading."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from another_mood.components.shared.json_data_model import (
    collect_files,
    deep_merge,
    load_model,
    load_schema,
    pluck,
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
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


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
    """load_model: read each JSON mapping and deep-merge them into a single dict."""

    def test_no_paths_returns_empty(self) -> None:
        assert load_model() == {}

    def test_loads_and_merges_json_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "builtin.json"
        f2 = tmp_path / "user.json"
        _write_json(f1, {"properties": {"prose": {"type": "array"}}})
        _write_json(f2, {"properties": {"users": {"type": "object"}}})

        assert load_model(f1, f2) == {
            "properties": {
                "prose": {"type": "array"},
                "users": {"type": "object"},
            }
        }

    def test_non_json_files_ignored(self, tmp_path: Path) -> None:
        # A stage dir holds blob bytes beside the records; only the
        # records are part of the model.
        d = tmp_path / "d"
        d.mkdir()
        _write_json(d / "data.json", {"key": "value"})
        (d / "photo.png").write_bytes(b"\x89PNG")
        _write_yaml(d / "leftover.yaml", {"key": "stale"})

        assert load_model(d) == {"key": "value"}

    def test_non_mapping_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "list.json"
        f.write_text('["a", "b"]')

        with pytest.raises(ValueError, match="Expected a JSON mapping"):
            load_model(f)


class TestLoadSchema:
    """load_schema: read each YAML schema document and deep-merge them."""

    def test_no_paths_returns_empty(self) -> None:
        assert load_schema() == {}

    def test_merges_builtin_and_user_schema(self, tmp_path: Path) -> None:
        builtin = tmp_path / "content-schema.yaml"
        user = tmp_path / "schema.yaml"
        _write_yaml(builtin, {"properties": {"prose": {"type": "array"}}})
        _write_yaml(user, {"properties": {"users": {"type": "array"}}})

        assert load_schema(builtin, user) == {
            "properties": {
                "prose": {"type": "array"},
                "users": {"type": "array"},
            }
        }

    def test_missing_path_skipped(self, tmp_path: Path) -> None:
        present = tmp_path / "content-schema.yaml"
        _write_yaml(present, {"properties": {"prose": {"type": "array"}}})

        assert load_schema(present, tmp_path / "absent.yaml") == {
            "properties": {"prose": {"type": "array"}}
        }


class TestSaveModel:
    """save_model: write a JSON file with project serialization conventions."""

    def test_round_trips_through_load_model(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        save_model(out, {"body": "line1\nline2\n", "n": 1, "flag": True})
        assert load_model(out) == {"body": "line1\nline2\n", "n": 1, "flag": True}

    def test_non_ascii_kept_readable(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        save_model(out, {"title": "日本語"})
        assert "日本語" in out.read_text(encoding="utf-8")

    def test_indented_for_post_mortem_reading(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        save_model(out, {"outer": {"inner": 1}})
        assert '\n  "outer": {\n    "inner": 1\n  }' in out.read_text()

    def test_drops_none_keys_recursively(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        save_model(out, {"keep": 1, "drop": None, "nested": {"keep": 2, "drop": None}})
        assert json.loads(out.read_text()) == {
            "keep": 1,
            "nested": {"keep": 2},
        }

    def test_value_outside_the_json_data_model_raises(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        with pytest.raises(TypeError):
            save_model(out, {"when": date(2026, 8, 1)})


class TestPluck:
    def test_flat_literal_key(self) -> None:
        assert pluck({"a": "v"}, "a") == "v"

    def test_dotted_path_into_nested_mapping(self) -> None:
        assert pluck({"a": {"b": "v"}}, "a.b") == "v"

    def test_flat_dotted_key_takes_precedence_over_nested(self) -> None:
        # When the record could be resolved either way, the longer literal
        # key wins.
        record: dict[str, Any] = {"a.b": "flat", "a": {"b": "nested"}}
        assert pluck(record, "a.b") == "flat"

    def test_partial_prefix_match_then_recurse_into_remainder(self) -> None:
        # Catalog edge ``a.b.c``; record carries flat ``a.b`` with ``c`` nested
        # inside.  Longest match consumes ``a.b`` first, then ``c``.
        assert pluck({"a.b": {"c": "v"}}, "a.b.c") == "v"

    def test_raises_when_no_prefix_matches(self) -> None:
        with pytest.raises(KeyError):
            pluck({"x": 1}, "missing")

    def test_raises_when_intermediate_value_is_scalar(self) -> None:
        with pytest.raises(KeyError):
            pluck({"a": 1}, "a.b")

    def test_returns_falsy_value_verbatim(self) -> None:
        # Bug-shield: ``None`` / ``False`` / ``0`` must surface as-is
        # rather than be folded into "missing".
        assert pluck({"a": False}, "a") is False
        assert pluck({"a": None}, "a") is None
        assert pluck({"a": 0}, "a") == 0
