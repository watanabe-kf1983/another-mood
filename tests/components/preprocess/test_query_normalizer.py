"""Tests for query_normalizer."""

from collections.abc import Mapping
from pathlib import Path

import yaml

from another_mood.components.preprocess.query_normalizer import (
    build_query_schema,
    normalize_queries,
)


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


class TestNormalizeQueries:
    """normalize_queries: component smoke test."""

    def test_validates_and_writes(self, tmp_path: Path) -> None:
        queries = tmp_path / "queries"
        queries.mkdir()
        (queries / "erds.yaml").write_text(
            "erds:\n  from: entities\n  select:\n    - item: name\n"
        )

        out = tmp_path / "normalized"
        normalize_queries(queries_dir=queries, out_dir=out)

        data = yaml.safe_load((out / "data" / "erds.yaml.yaml").read_text())
        assert data == {
            "__definition": {
                "queries": [
                    {"id": "erds", "from": "entities", "select": [{"item": "name"}]}
                ]
            }
        }
