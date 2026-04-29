"""Tests for query_deriver."""

from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

from another_mood.components.preprocess.query_deriver import (
    build_query_schema,
    derive_queries,
)
from another_mood.components.shared.diagnostic import FileValidationError

_CATALOG_YAML = (
    "__definition:\n"
    "  entities:\n"
    "    - id: items\n"
    "      item_type:\n"
    "        id: items.item\n"
    "        attributes:\n"
    "          - {id: name, type: string, required: true}\n"
    "          - {id: phase, type: string, required: true}\n"
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


class TestIdentifierDiagnostics:
    """derive_queries reports identifier mismatches as Diagnostics pointing
    back at the originating YAML position, and writes nothing on failure."""

    def _run(self, tmp_path: Path, query_yaml: str) -> Path:
        # Calls the underlying function directly to bypass the Component
        # wrapper's error-propagation context, so FileValidationError
        # surfaces to the test rather than being captured into a build
        # report.
        _write(tmp_path / "queries" / "q.yaml", query_yaml)
        _write(tmp_path / "catalog" / "schema.yaml", _CATALOG_YAML)
        out = tmp_path / "out"
        derive_queries.fn(
            queries_dir=tmp_path / "queries",
            data_catalog_dir=tmp_path / "catalog",
            out_dir=out,
        )
        return out

    def test_unknown_from_points_at_the_from_value(self, tmp_path: Path) -> None:
        query_yaml = (
            "names:\n"  # line 1
            "  from: missing\n"  # line 2, value column 9
            "  select:\n"
            "    - item: name\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            self._run(tmp_path, query_yaml)
        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].file == tmp_path / "queries" / "q.yaml"
        assert diags[0].line == 2
        assert diags[0].column == 9
        assert "missing" in diags[0].message

    def test_unknown_grouped_by_points_at_the_by_value(self, tmp_path: Path) -> None:
        query_yaml = (
            "by_phase:\n"  # line 1
            "  from: items\n"  # line 2
            "  grouped:\n"  # line 3
            "    by: nope\n"  # line 4, value column 9
            "  select:\n"
            "    - item: phase\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            self._run(tmp_path, query_yaml)
        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].line == 4
        assert diags[0].column == 9
        assert "nope" in diags[0].message

    def test_unknown_select_item_points_at_the_item_value(self, tmp_path: Path) -> None:
        query_yaml = (
            "names:\n"  # line 1
            "  from: items\n"  # line 2
            "  select:\n"  # line 3
            "    - item: ghost\n"  # line 4, value column 13
        )
        with pytest.raises(FileValidationError) as exc_info:
            self._run(tmp_path, query_yaml)
        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].line == 4
        assert diags[0].column == 13
        assert "ghost" in diags[0].message

    def test_multiple_errors_across_queries_are_collected(self, tmp_path: Path) -> None:
        query_yaml = (
            "first:\n"
            "  from: missing_a\n"
            "  select:\n"
            "    - item: name\n"
            "second:\n"
            "  from: missing_b\n"
            "  select:\n"
            "    - item: name\n"
        )
        with pytest.raises(FileValidationError) as exc_info:
            self._run(tmp_path, query_yaml)
        messages = [d.message for d in exc_info.value.diagnostics]
        assert len(messages) == 2
        assert any("missing_a" in m for m in messages)
        assert any("missing_b" in m for m in messages)

    def test_no_output_written_when_diagnostics_present(self, tmp_path: Path) -> None:
        query_yaml = "names:\n  from: missing\n  select:\n    - item: name\n"
        with pytest.raises(FileValidationError):
            self._run(tmp_path, query_yaml)
        # The pipeline raises before any save_model call.
        assert not list((tmp_path / "derived" / "data").rglob("*.yaml"))
