"""Tests for query_deriver."""

from collections.abc import Mapping
from pathlib import Path

import yaml

from another_mood.components.preprocess.query_deriver import (
    build_query_schema,
    derive_queries,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestBuildQuerySchema:
    """build_query_schema: validate against built-in QuerySchema."""

    def _validate(self, data: Mapping[str, object]) -> list[object]:
        from another_mood.components.preprocess.validator import Validator

        validator = Validator(build_query_schema())
        return list(validator.validate(data, Path("test.yaml")))

    def test_valid_query_accepted(self) -> None:
        data = {"q": {"from": "items", "select": [{"item": "name"}]}}
        assert self._validate(data) == []

    def test_from_only_accepted(self) -> None:
        data = {"q": {"from": "items"}}
        assert self._validate(data) == []

    def test_missing_from_rejected(self) -> None:
        data = {"q": {"select": [{"item": "name"}]}}
        assert len(self._validate(data)) >= 1

    def test_unknown_key_rejected(self) -> None:
        data = {"q": {"from": "items", "unknown": "value"}}
        assert len(self._validate(data)) >= 1

    def test_select_missing_item_rejected(self) -> None:
        data = {"q": {"from": "items", "select": [{"as": "alias"}]}}
        assert len(self._validate(data)) >= 1

    def test_unicode_query_name_accepted(self) -> None:
        data = {"クエリ": {"from": "items"}}
        assert self._validate(data) == []

    def test_hyphenated_query_name_rejected(self) -> None:
        data = {"my-query": {"from": "items"}}
        assert len(self._validate(data)) >= 1


class TestDeriveQueries:
    """derive_queries: component smoke test."""

    def test_emits_queries_and_derived_entities(self, tmp_path: Path) -> None:
        queries = tmp_path / "queries"
        _write(
            queries / "names.yaml",
            "names:\n  from: items\n  select:\n    - item: name\n",
        )

        data_catalog = tmp_path / "data-catalog" / "data"
        _write(
            data_catalog / "schema.yaml",
            "__definition:\n"
            "  entities:\n"
            "    - id: items\n"
            "      item_type:\n"
            "        id: items.item\n"
            "        attributes:\n"
            "          - {id: name, type: string, required: true}\n",
        )

        out = tmp_path / "derived"
        derive_queries(
            queries_dir=queries,
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        data = yaml.safe_load((out / "data" / "names.yaml.yaml").read_text())
        assert data == {
            "__definition": {
                "queries": [
                    {"id": "names", "from": "items", "select": [{"item": "name"}]}
                ],
                "entities": [
                    {
                        "id": "names",
                        "item_type": {
                            "id": "names.item",
                            "attributes": [
                                {"id": "name", "type": "string", "required": True}
                            ],
                        },
                        "builtin": False,
                        "view": True,
                    }
                ],
            }
        }

    def test_empty_queries_emits_empty_definition(self, tmp_path: Path) -> None:
        queries = tmp_path / "queries"
        queries.mkdir()
        (tmp_path / "data-catalog" / "data").mkdir(parents=True)

        out = tmp_path / "derived"
        derive_queries(
            queries_dir=queries,
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        # No source files produces no output files (data dir exists, but is empty).
        assert not list((out / "data").rglob("*.yaml"))
