"""Tests for Composer — passthrough copy and query evaluation."""

from pathlib import Path
from typing import Any

import yaml

from reqs_builder.composer import compose, parse_query
from reqs_builder.query import From, Grouped, Query, Select, SelectItem


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestCompose:
    def test_passthrough_and_query(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents"
        contents.mkdir()
        _write_yaml(
            contents / "items.yaml",
            {"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]},
        )

        queries = tmp_path / "queries"
        queries.mkdir()
        _write_yaml(
            queries / "names.yaml",
            {
                "names": {
                    "from": "items",
                    "select": [{"item": "name"}],
                }
            },
        )

        out = tmp_path / "views"
        compose(contents, queries, out)

        # Passthrough
        assert yaml.safe_load((out / "items.yaml").read_text()) == {
            "items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]
        }

        # Query result
        assert yaml.safe_load((out / "names.yaml").read_text()) == {
            "names": [{"name": "a"}, {"name": "b"}]
        }

    def test_empty_queries_dir(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents"
        contents.mkdir()
        _write_yaml(contents / "data.yaml", {"key": "value"})

        queries = tmp_path / "queries"
        queries.mkdir()

        out = tmp_path / "views"
        compose(contents, queries, out)

        assert yaml.safe_load((out / "data.yaml").read_text()) == {"key": "value"}


class TestParseQuery:
    def test_full_query(self) -> None:
        raw = {
            "from": "entities",
            "grouped": {"by": "category", "as": "items"},
            "select": [
                {"item": "category", "as": "id"},
                {"item": "category"},
            ],
        }
        assert parse_query(raw) == Query(
            select=Select(
                items=[
                    SelectItem(item="category", as_name="id"),
                    SelectItem(item="category", as_name="category"),
                ]
            ),
            from_clause=From(source="entities"),
            grouped=Grouped(by="category", as_name="items"),
        )

    def test_grouped_as_defaults_to_from_name(self) -> None:
        raw = {
            "from": "entities",
            "grouped": {"by": "category"},
            "select": [{"item": "category"}],
        }
        assert parse_query(raw).grouped == Grouped(by="category", as_name="entities")

    def test_without_grouped(self) -> None:
        raw = {
            "from": "items",
            "select": [{"item": "name"}],
        }
        assert parse_query(raw).grouped is None

    def test_select_item_as_defaults_to_item(self) -> None:
        raw = {
            "from": "items",
            "select": [{"item": "name"}],
        }
        assert parse_query(raw).select == Select(
            items=[SelectItem(item="name", as_name="name")]
        )
