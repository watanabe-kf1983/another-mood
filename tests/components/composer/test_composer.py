"""Tests for Composer — passthrough copy and query evaluation."""

from pathlib import Path

import yaml

from reqs_builder.components.composer.composer import compose, parse_query
from reqs_builder.components.composer.query import (
    From,
    Grouped,
    Query,
    Select,
    SelectItem,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestCompose:
    def test_passthrough_and_query(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents"
        _write(
            contents / "items.yaml",
            "items:\n  - {name: a, value: 1}\n  - {name: b, value: 2}\n",
        )
        # __build_report.yaml from upstream stages must NOT be passed through.
        _write(
            contents / "__build_report.yaml",
            "__build_report: {normalize_contents: {result: ok}}\n",
        )

        queries = tmp_path / "queries"
        _write(
            queries / "name_query.yaml",
            "__definition:\n"
            "  queries:\n"
            "    - id: names\n"
            "      from: items\n"
            "      select:\n"
            "        - {item: name}\n",
        )

        data_catalog = tmp_path / "data-catalog"
        _write(
            data_catalog / "schema.yaml",
            "__definition:\n  entities:\n    - {id: items, fields: []}\n",
        )

        out = tmp_path / "views"
        compose(
            contents_dir=contents,
            queries_dir=queries,
            data_catalog_dir=data_catalog,
            out_dir=out,
        )

        # Passthrough: each input file is copied bytewise into a dedicated subdir.
        # __build_report.yaml is filtered out because it belongs to error
        # propagation, not the user-visible data.
        for src, sub in (
            (contents, "contents"),
            (data_catalog, "data-catalog"),
            (queries, "queries"),
        ):
            for f in src.rglob("*.yaml"):
                dst = out / sub / f.relative_to(src)
                if f.name == "__build_report.yaml":
                    assert not dst.exists()
                else:
                    assert dst.read_text() == f.read_text()

        # Query result.
        assert yaml.safe_load(
            (out / "query-results" / "names.yaml").read_text()
        ) == yaml.safe_load("names:\n  - {name: a}\n  - {name: b}\n")

    def test_empty_queries_dir(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents"
        _write(contents / "data.yaml", "key: value\n")

        queries = tmp_path / "queries"
        queries.mkdir()

        data_catalog = tmp_path / "data-catalog"
        data_catalog.mkdir()

        out = tmp_path / "views"
        compose(
            contents_dir=contents,
            queries_dir=queries,
            data_catalog_dir=data_catalog,
            out_dir=out,
        )

        assert (out / "contents" / "data.yaml").read_text() == "key: value\n"


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
