"""Tests for query_normalizer.normalize_query and its clause helpers.

Each clause has a focused class; ``TestNormalizeQuery`` covers the
record-level entry point and absent-clause pass-through.  A separate
``TestPreservesUserStr`` block asserts that user-input provenance
travels through normalization, which the downstream
``QueryDeriveError`` diagnostic relies on.
"""

from pathlib import Path

import pytest

from another_mood.components.preprocess.query_normalizer import (
    normalize_flatten,
    normalize_grouped,
    normalize_inline_flatten,
    normalize_join,
    normalize_query,
    normalize_select,
    normalize_sort,
)
from another_mood.components.preprocess.source_loader import Location, UserStr


class TestNormalizeFlatten:
    def test_shorthand_string(self) -> None:
        assert normalize_flatten("tasks") == [
            {"of": "tasks", "as": "tasks", "preserve_empty": False}
        ]

    def test_object_form_full(self) -> None:
        assert normalize_flatten(
            {"of": "tasks", "as": "task", "preserve_empty": True}
        ) == [{"of": "tasks", "as": "task", "preserve_empty": True}]

    def test_object_form_as_defaults_to_of(self) -> None:
        assert normalize_flatten({"of": "tasks"}) == [
            {"of": "tasks", "as": "tasks", "preserve_empty": False}
        ]

    def test_object_form_preserve_empty_defaults_to_false(self) -> None:
        assert normalize_flatten({"of": "tasks", "as": "task"}) == [
            {"of": "tasks", "as": "task", "preserve_empty": False}
        ]

    def test_list_form_mixes_shorthand_and_object(self) -> None:
        assert normalize_flatten(["hobbies", {"of": "pets", "as": "pet"}]) == [
            {"of": "hobbies", "as": "hobbies", "preserve_empty": False},
            {"of": "pets", "as": "pet", "preserve_empty": False},
        ]

    def test_rejects_unsupported_shape(self) -> None:
        with pytest.raises(TypeError, match="flatten clause"):
            normalize_flatten(42)


class TestNormalizeJoin:
    """``normalize_join`` (clause-level dispatch: mapping vs list)."""

    def test_single_mapping_wraps_in_list(self) -> None:
        assert normalize_join(
            {"to": "tasks", "on": {"left": "id", "right": "cat"}}
        ) == [
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "tasks",
            }
        ]

    def test_list_form_preserves_order(self) -> None:
        result = normalize_join(
            [
                {"to": "tasks", "on": {"left": "id", "right": "cat"}},
                {"to": "tags", "on": {"left": "tag_id", "right": "id"}},
            ]
        )
        assert [entry["to"] for entry in result] == ["tasks", "tags"]

    def test_as_defaults_to_to(self) -> None:
        [entry] = normalize_join({"to": "tasks", "on": {"left": "id", "right": "cat"}})
        assert entry["as"] == "tasks"

    def test_explicit_as_kept(self) -> None:
        [entry] = normalize_join(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "owned_tasks",
            }
        )
        assert entry["as"] == "owned_tasks"

    def test_where_passed_through(self) -> None:
        [entry] = normalize_join(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "where": {"open": True},
            }
        )
        assert entry["where"] == {"open": True}

    def test_where_absent_stays_absent(self) -> None:
        [entry] = normalize_join({"to": "tasks", "on": {"left": "id", "right": "cat"}})
        assert "where" not in entry

    def test_inline_flatten_shorthand_expanded(self) -> None:
        [entry] = normalize_join(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "flatten": True,
            }
        )
        assert entry["flatten"] == {
            "of": "tasks",
            "as": "tasks",
            "preserve_empty": False,
        }

    def test_inline_flatten_object_form_of_fixed_to_join_as(self) -> None:
        [entry] = normalize_join(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "owned_tasks",
                "flatten": {"as": "task", "preserve_empty": True},
            }
        )
        # ``of`` is forced to the join's ``as`` (unwind target is the
        # just-attached array), not the user-supplied right-side ``to``.
        assert entry["flatten"] == {
            "of": "owned_tasks",
            "as": "task",
            "preserve_empty": True,
        }

    def test_inline_flatten_empty_mapping_defaults_both(self) -> None:
        [entry] = normalize_join(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "owned_tasks",
                "flatten": {},
            }
        )
        assert entry["flatten"] == {
            "of": "owned_tasks",
            "as": "owned_tasks",
            "preserve_empty": False,
        }

    def test_flatten_absent_stays_absent(self) -> None:
        [entry] = normalize_join({"to": "tasks", "on": {"left": "id", "right": "cat"}})
        assert "flatten" not in entry

    def test_rejects_unsupported_shape(self) -> None:
        with pytest.raises(TypeError, match="join clause"):
            normalize_join(42)


class TestNormalizeInlineFlatten:
    def test_true_uses_join_as_for_of_and_as(self) -> None:
        assert normalize_inline_flatten(True, "owned_tasks") == {
            "of": "owned_tasks",
            "as": "owned_tasks",
            "preserve_empty": False,
        }


class TestNormalizeGrouped:
    def test_explicit_as_kept(self) -> None:
        assert normalize_grouped(
            {"by": "category", "as": "items"}, from_="entities"
        ) == {"by": "category", "as": "items"}

    def test_as_defaults_to_last_segment_of_from(self) -> None:
        assert normalize_grouped({"by": "category"}, from_="__definition.entities") == {
            "by": "category",
            "as": "entities",
        }

    def test_as_defaults_to_from_when_from_has_no_dot(self) -> None:
        assert normalize_grouped({"by": "category"}, from_="items") == {
            "by": "category",
            "as": "items",
        }


class TestNormalizeSelect:
    def test_as_defaults_to_item(self) -> None:
        assert normalize_select([{"item": "name"}]) == [{"item": "name", "as": "name"}]

    def test_explicit_as_kept(self) -> None:
        assert normalize_select([{"item": "category", "as": "id"}]) == [
            {"item": "category", "as": "id"}
        ]

    def test_preserves_order(self) -> None:
        result = normalize_select([{"item": "a"}, {"item": "b"}, {"item": "c"}])
        assert [e["item"] for e in result] == ["a", "b", "c"]

    def test_empty_list(self) -> None:
        assert normalize_select([]) == []


class TestNormalizeSort:
    def test_fills_direction_and_missing_defaults(self) -> None:
        assert normalize_sort({"by": "phase"}) == {
            "by": "phase",
            "direction": "asc",
            "missing": "last",
        }

    def test_explicit_direction_kept(self) -> None:
        assert normalize_sort({"by": "phase", "direction": "desc"}) == {
            "by": "phase",
            "direction": "desc",
            "missing": "last",
        }

    def test_explicit_missing_kept(self) -> None:
        assert normalize_sort({"by": "phase", "missing": "first"}) == {
            "by": "phase",
            "direction": "asc",
            "missing": "first",
        }


class TestNormalizeQuery:
    """Record-level entry point: dispatches per clause and skips absent ones."""

    def test_minimal_query_passes_through(self) -> None:
        assert normalize_query({"id": "q", "from": "items"}) == {
            "id": "q",
            "from": "items",
        }

    def test_all_clauses_normalized(self) -> None:
        raw = {
            "id": "q",
            "from": "entities",
            "flatten": "tags",
            "join": {"to": "tasks", "on": {"left": "id", "right": "cat"}},
            "where": {"open": True},
            "grouped": {"by": "category"},
            "select": [{"item": "name"}],
            "sort": {"by": "name"},
        }
        assert normalize_query(raw) == {
            "id": "q",
            "from": "entities",
            "flatten": [{"of": "tags", "as": "tags", "preserve_empty": False}],
            "join": [
                {
                    "to": "tasks",
                    "on": {"left": "id", "right": "cat"},
                    "as": "tasks",
                }
            ],
            "where": {"open": True},
            "grouped": {"by": "category", "as": "entities"},
            "select": [{"item": "name", "as": "name"}],
            "sort": {"by": "name", "direction": "asc", "missing": "last"},
        }

    def test_absent_clauses_stay_absent(self) -> None:
        result = normalize_query({"id": "q", "from": "items"})
        for key in ("flatten", "join", "where", "grouped", "select", "sort"):
            assert key not in result

    def test_where_is_passed_through_unchanged(self) -> None:
        # ``where`` keeps its original sugar (e.g. scalar-as-eq) since the
        # typed predicate AST is built later by ``parse_record_predicate``.
        where = {"phase": "design", "and": [{"open": True}]}
        result = normalize_query({"id": "q", "from": "items", "where": where})
        assert result["where"] is where


class TestPreservesUserStr:
    """Identifiers from user input must keep their source ``Location``
    so ``QueryDeriveError`` diagnostics can point back at the YAML.
    """

    @staticmethod
    def _u(value: str, line: int = 1, column: int = 1) -> UserStr:
        return UserStr(value, Location(file=Path("x.yaml"), line=line, column=column))

    def test_flatten_shorthand_preserves_userstr(self) -> None:
        of = self._u("tasks", line=3)
        [entry] = normalize_flatten(of)
        # Both ``of`` and the defaulted ``as`` reuse the original
        # UserStr — the only string in the input — so a downstream
        # diagnostic can point back at line 3.
        assert isinstance(entry["of"], UserStr)
        assert isinstance(entry["as"], UserStr)
        assert entry["of"].location.line == 3  # type: ignore[union-attr]
        assert entry["as"].location.line == 3  # type: ignore[union-attr]

    def test_flatten_object_form_default_as_reuses_of_userstr(self) -> None:
        of = self._u("tasks", line=5)
        [entry] = normalize_flatten({"of": of})
        assert entry["as"] is of

    def test_join_default_as_reuses_to_userstr(self) -> None:
        to = self._u("tasks", line=7)
        [entry] = normalize_join({"to": to, "on": {"left": "id", "right": "cat"}})
        assert entry["as"] is to

    def test_select_default_as_reuses_item_userstr(self) -> None:
        item = self._u("name", line=9)
        [entry] = normalize_select([{"item": item}])
        assert entry["as"] is item
