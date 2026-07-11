"""Tests for query_deriver."""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from another_mood.components.preprocess.query_deriver import (
    _source_name_conflicts,  # pyright: ignore[reportPrivateUsage]
    build_query_schema,
    derive_queries,
)
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.user_source.diagnostic import FileValidationError
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.query import Query

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
    path.write_text(text, encoding="utf-8")


def _write_catalog(catalog_dir: Path, *extra_yaml: str) -> None:
    """Write a data-catalog dir including the ``__definition.*`` entries.

    Built-in queries reference ``__definition.entities`` and
    ``__definition.queries``; tests that exercise ``derive_queries``
    need these entries so the bundled built-in queries pass
    ``derive``-time validation.  Mirrors what
    ``schema_inspector._emit_definition_catalog`` writes in the real
    pipeline — kept linked through the dataclass ``catalog`` ClassVars
    rather than a literal YAML constant so changes to those classes
    propagate to the fixture automatically.
    """
    entities = [
        *dc.flatten_tree(dc.Entity.catalog, "__definition.entities"),
        *dc.flatten_tree(Query.catalog, "__definition.queries"),
    ]
    save_model(
        catalog_dir / "data" / "__builtin" / "__definition.yaml",
        {
            "__definition": {
                "entities": [replace(e, builtin=True).to_dict() for e in entities],
            }
        },
    )
    for i, text in enumerate(extra_yaml):
        _write(catalog_dir / "data" / f"extra_{i}.yaml", text)


class TestBuildQuerySchema:
    """build_query_schema: validate against built-in QuerySchema."""

    def _validate(self, data: Mapping[str, object]) -> list[object]:
        from another_mood.components.shared.user_source.validator import Validator

        validator = Validator(build_query_schema())
        return list(validator.validate(data))

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

        _write_catalog(
            tmp_path / "data-catalog",
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
                    {
                        "id": "names",
                        "from": "items",
                        "select": [{"item": "name", "as": "name"}],
                    }
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

    def test_query_body_passes_through_untouched(self, tmp_path: Path) -> None:
        """Query body passes through the normalizer verbatim — the
        schema-driven normalizer stops at the top level."""
        queries = tmp_path / "queries"
        _write(
            queries / "filtered.yaml",
            "phase10:\n"
            "  from: items\n"
            "  where:\n"
            "    phase:\n"
            "      eq: '10'\n"
            "  select:\n"
            "    - item: name\n",
        )
        _write_catalog(
            tmp_path / "data-catalog",
            "__definition:\n"
            "  entities:\n"
            "    - id: items\n"
            "      item_type:\n"
            "        id: items.item\n"
            "        attributes:\n"
            "          - {id: name, type: string, required: true}\n"
            "          - {id: phase, type: string, required: true}\n",
        )

        out = tmp_path / "derived"
        derive_queries(
            queries_dir=queries,
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        data = yaml.safe_load((out / "data" / "filtered.yaml.yaml").read_text())
        assert data["__definition"]["queries"] == [
            {
                "id": "phase10",
                "from": "items",
                "where": {"phase": {"eq": "10"}},
                "select": [{"item": "name", "as": "name"}],
            }
        ]

    def test_empty_user_queries_still_emits_builtin(self, tmp_path: Path) -> None:
        """Built-in queries are processed regardless of user input.

        With no user queries provided, the merged output must still
        contain the bundled built-in queries — the built-in __root
        template depends on them — and each must have produced a
        ``view: true`` derivation entry.  Asserts the invariant on the
        merged ``__definition`` document so the test does not pin the
        specific set of bundled queries.
        """
        queries = tmp_path / "queries"
        queries.mkdir()
        _write_catalog(tmp_path / "data-catalog")

        out = tmp_path / "derived"
        derive_queries(
            queries_dir=queries,
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        merged = load_model(out / "data")["__definition"]
        derived_query_ids = {q["id"] for q in merged["queries"]}
        derived_view_ids = {e["id"] for e in merged["entities"] if e["view"]}
        # Every bundled query produces a same-named view entity.  Extra
        # descendant view entities (e.g. from grouped or from selecting an
        # entity-typed singleton) are allowed.
        assert derived_query_ids
        assert derived_query_ids <= derived_view_ids


class TestIdentifierDiagnostics:
    """derive_queries reports identifier mismatches as Diagnostics pointing
    back at the originating YAML position, and writes nothing on failure."""

    def _run(self, tmp_path: Path, query_yaml: str) -> Path:
        # Calls the underlying function directly to bypass the Component
        # wrapper's error-propagation context, so FileValidationError
        # surfaces to the test rather than being captured into a build
        # report.
        _write(tmp_path / "queries" / "q.yaml", query_yaml)
        _write_catalog(tmp_path / "catalog", _CATALOG_YAML)
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


class TestSourceNameConflicts:
    """_source_name_conflicts: shadowing detection over a flat name list.

    A query name shadows another source when it reuses a catalog entity
    id, repeats an earlier query name, or takes the reserved ``__``
    built-in prefix.  Each conflict is reported as ``(message, name)``.
    """

    _ENTITY_IDS = frozenset({"items", "albums"})

    def _conflicts(self, names: list[str]) -> list[tuple[str, str]]:
        return _source_name_conflicts(names, self._ENTITY_IDS)

    def test_distinct_names_have_no_conflict(self) -> None:
        assert self._conflicts(["ranked", "named"]) == []

    def test_entity_collision(self) -> None:
        assert self._conflicts(["items"]) == [
            ("query name 'items' collides with data entity 'items'", "items")
        ]

    def test_duplicate_reports_only_the_later_occurrence(self) -> None:
        assert self._conflicts(["ranked", "named", "ranked"]) == [
            ("duplicate query name 'ranked'", "ranked")
        ]

    def test_reserved_prefix(self) -> None:
        assert self._conflicts(["__mine"]) == [
            ("query name '__mine' is reserved: '__' marks built-in names", "__mine")
        ]

    def test_reserved_prefix_takes_precedence_over_entity_collision(self) -> None:
        # An entity can never be named ``__items`` (schema forbids it), but
        # the ordering still matters: the ``__`` check runs first.
        assert self._conflicts(["__items"]) == [
            ("query name '__items' is reserved: '__' marks built-in names", "__items")
        ]

    def test_conflicts_preserve_input_order(self) -> None:
        messages = [name for _, name in self._conflicts(["items", "__x", "ok", "ok"])]
        assert messages == ["items", "__x", "ok"]


class TestSourceNameDiagnostics:
    """derive_queries surfaces a source-name conflict as a positioned
    diagnostic anchored at the query name's YAML key."""

    def test_collision_points_at_the_query_key(self, tmp_path: Path) -> None:
        _write(tmp_path / "queries" / "q.yaml", "items:\n  from: items\n")
        _write_catalog(tmp_path / "catalog", _CATALOG_YAML)
        with pytest.raises(FileValidationError) as exc_info:
            derive_queries.fn(
                queries_dir=tmp_path / "queries",
                data_catalog_dir=tmp_path / "catalog",
                out_dir=tmp_path / "out",
            )
        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert diags[0].file == tmp_path / "queries" / "q.yaml"
        assert diags[0].line == 1
        assert diags[0].column == 1  # the query name key, not the ``from:`` value
        assert "collides with data entity 'items'" in diags[0].message

    def test_name_conflict_short_circuits_derivation(self, tmp_path: Path) -> None:
        # The ``items`` query both shadows the entity ``items`` (a name
        # conflict) and reads a missing source (a derive-time error).
        # Fail-fast reports only the name conflict: deriving over an
        # ambiguous namespace is unreliable, so name checking short-circuits
        # before derivation runs.
        _write(tmp_path / "queries" / "q.yaml", "items:\n  from: missing\n")
        _write_catalog(tmp_path / "catalog", _CATALOG_YAML)
        with pytest.raises(FileValidationError) as exc_info:
            derive_queries.fn(
                queries_dir=tmp_path / "queries",
                data_catalog_dir=tmp_path / "catalog",
                out_dir=tmp_path / "out",
            )
        diags = exc_info.value.diagnostics
        assert len(diags) == 1
        assert "collides with data entity 'items'" in diags[0].message
