"""Tests for JSON data model — deep merge and YAML loading."""

from pathlib import Path
from typing import Any

import yaml

from reqs_builder.components.shared.json_data_model import deep_merge, load_yamls


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


class TestLoadYamls:
    def test_single_file(self, tmp_path: Path) -> None:
        d = tmp_path / "views"
        d.mkdir()
        _write_yaml(d / "entities.yaml", {"entities": [{"id": "user", "name": "User"}]})

        assert load_yamls(d) == {
            "entities": [{"id": "user", "name": "User"}],
        }

    def test_merges_multiple_files(self, tmp_path: Path) -> None:
        d = tmp_path / "views"
        d.mkdir()
        _write_yaml(d / "entities.yaml", {"entities": [{"id": "user"}]})
        _write_yaml(
            d / "relations.yaml",
            {"relations": [{"from": "user", "to": "role"}]},
        )

        result = load_yamls(d)
        assert list(result.keys()) == ["entities", "relations"]

    def test_empty_dir_returns_empty_dict(self, tmp_path: Path) -> None:
        d = tmp_path / "views"
        d.mkdir()

        assert load_yamls(d) == {}

    def test_non_yaml_files_ignored(self, tmp_path: Path) -> None:
        d = tmp_path / "views"
        d.mkdir()
        (d / "readme.md").write_text("# Not YAML")
        _write_yaml(d / "data.yaml", {"key": "value"})

        assert load_yamls(d) == {"key": "value"}

    def test_loads_subdirectory_yaml(self, tmp_path: Path) -> None:
        d = tmp_path / "views"
        d.mkdir()
        _write_yaml(d / "top.yaml", {"prose": [{"id": "top"}]})
        _write_yaml(d / "sub" / "nested.yaml", {"prose": [{"id": "sub/nested"}]})

        result = load_yamls(d)
        assert result == {"prose": [{"id": "sub/nested"}, {"id": "top"}]}

    def test_multiple_directories(self, tmp_path: Path) -> None:
        d1 = tmp_path / "contents"
        d2 = tmp_path / "queries"
        d1.mkdir()
        d2.mkdir()
        _write_yaml(d1 / "entities.yaml", {"entities": [{"id": "user"}]})
        _write_yaml(d2 / "query.yaml", {"queries": [{"name": "q1"}]})

        result = load_yamls(d1, d2)
        assert result == {
            "entities": [{"id": "user"}],
            "queries": [{"name": "q1"}],
        }

    def test_multiple_directories_deep_merged(self, tmp_path: Path) -> None:
        d1 = tmp_path / "a"
        d2 = tmp_path / "b"
        d1.mkdir()
        d2.mkdir()
        _write_yaml(d1 / "data.yaml", {"items": [{"id": "x"}]})
        _write_yaml(d2 / "data.yaml", {"items": [{"id": "y"}]})

        result = load_yamls(d1, d2)
        assert result == {"items": [{"id": "x"}, {"id": "y"}]}

    def test_nonexistent_directory_skipped(self, tmp_path: Path) -> None:
        d1 = tmp_path / "exists"
        d2 = tmp_path / "missing"
        d1.mkdir()
        _write_yaml(d1 / "data.yaml", {"key": "value"})

        assert load_yamls(d1, d2) == {"key": "value"}

    def test_no_directories_returns_empty(self) -> None:
        assert load_yamls() == {}
