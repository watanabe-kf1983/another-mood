"""Tests for Query DSL — object model and evaluation."""

import pytest

from another_mood.components.composer.query import (
    From,
    Grouped,
    Query,
    Select,
    SelectItem,
    flatten_children,
)


class TestFlattenChildren:
    def test_array_of_objects_extends(self) -> None:
        parents = [{"k": [{"id": "1"}, {"id": "2"}]}]
        assert list(flatten_children(parents, "k")) == [{"id": "1"}, {"id": "2"}]

    def test_single_object_is_one_element(self) -> None:
        parents = [{"k": {"id": "1"}}]
        assert list(flatten_children(parents, "k")) == [{"id": "1"}]

    def test_deep_nested_arrays_flatten(self) -> None:
        parents = [{"k": [[{"id": "a"}, {"id": "b"}], [{"id": "c"}]]}]
        assert list(flatten_children(parents, "k")) == [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]

    def test_concatenates_across_parents(self) -> None:
        parents = [{"k": [{"id": "1"}]}, {"k": {"id": "2"}}]
        assert list(flatten_children(parents, "k")) == [{"id": "1"}, {"id": "2"}]

    def test_raises_on_missing_key(self) -> None:
        with pytest.raises(KeyError):
            flatten_children([{"k": []}], "missing")


class TestFrom:
    def test_single_segment(self) -> None:
        sources = {"entities": [{"id": "user"}, {"id": "role"}]}
        assert list(From(path=["entities"]).apply([sources])) == [
            {"id": "user"},
            {"id": "role"},
        ]

    def test_multi_segment_chains_flattens(self) -> None:
        sources = {
            "categories": [
                {"id": "A", "tasks": [{"id": "A1"}, {"id": "A2"}]},
                {"id": "B", "tasks": [{"id": "B1"}]},
            ]
        }
        assert list(From(path=["categories", "tasks"]).apply([sources])) == [
            {"id": "A1"},
            {"id": "A2"},
            {"id": "B1"},
        ]


class TestSelectItem:
    def test_extracts_field(self) -> None:
        assert SelectItem(item="name", as_name="name").apply({"name": "Alice"}) == (
            "name",
            "Alice",
        )

    def test_renames_field(self) -> None:
        assert SelectItem(item="category", as_name="id").apply(
            {"category": "user-management"}
        ) == ("id", "user-management")

    def test_raises_on_missing_field(self) -> None:
        with pytest.raises(KeyError):
            SelectItem(item="missing", as_name="x").apply({"name": "Alice"})


class TestSelect:
    def test_projects_fields(self) -> None:
        select = Select(
            items=[
                SelectItem(item="category", as_name="id"),
                SelectItem(item="category", as_name="category"),
            ]
        )
        records = [{"category": "a", "extra": 1}, {"category": "b", "extra": 2}]
        assert list(select.apply(records)) == [
            {"id": "a", "category": "a"},
            {"id": "b", "category": "b"},
        ]

    def test_empty_records(self) -> None:
        select = Select(items=[SelectItem(item="x", as_name="x")])
        assert list(select.apply([])) == []


class TestGrouped:
    def test_groups_by_key(self) -> None:
        records = [
            {"id": "user", "category": "a"},
            {"id": "role", "category": "a"},
            {"id": "order", "category": "b"},
        ]
        expected = [
            {
                "category": "a",
                "entities": [
                    {"id": "user", "category": "a"},
                    {"id": "role", "category": "a"},
                ],
            },
            {
                "category": "b",
                "entities": [{"id": "order", "category": "b"}],
            },
        ]
        assert (
            list(Grouped(by="category", as_name="entities").apply(records)) == expected
        )

    def test_preserves_insertion_order(self) -> None:
        records = [
            {"id": "1", "cat": "b"},
            {"id": "2", "cat": "a"},
            {"id": "3", "cat": "b"},
        ]
        result = Grouped(by="cat", as_name="items").apply(records)
        assert [r["cat"] for r in result] == ["b", "a"]

    def test_raises_on_missing_key(self) -> None:
        with pytest.raises(KeyError):
            Grouped(by="missing", as_name="items").apply([{"id": "x"}])


class TestQuery:
    def test_example_project_erds(self) -> None:
        """Matches the ecommerce example query: group entities by category."""
        sources = {
            "entities": [
                {"id": "user", "name": "ユーザー", "category": "user-management"},
                {"id": "role", "name": "ロール", "category": "user-management"},
                {"id": "order", "name": "注文", "category": "order-management"},
            ]
        }
        query = Query(
            select=Select(
                items=[
                    SelectItem(item="category", as_name="id"),
                    SelectItem(item="category", as_name="category"),
                    SelectItem(item="entities", as_name="entities"),
                ]
            ),
            from_clause=From(path=["entities"]),
            grouped=Grouped(by="category", as_name="entities"),
        )
        expected = [
            {
                "id": "user-management",
                "category": "user-management",
                "entities": [
                    {"id": "user", "name": "ユーザー", "category": "user-management"},
                    {"id": "role", "name": "ロール", "category": "user-management"},
                ],
            },
            {
                "id": "order-management",
                "category": "order-management",
                "entities": [
                    {"id": "order", "name": "注文", "category": "order-management"},
                ],
            },
        ]
        assert list(query.apply([sources])) == expected

    def test_without_grouped(self) -> None:
        sources = {"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}
        query = Query(
            select=Select(items=[SelectItem(item="name", as_name="name")]),
            from_clause=From(path=["items"]),
            grouped=None,
        )
        assert list(query.apply([sources])) == [{"name": "a"}, {"name": "b"}]

    def test_dot_path_in_from(self) -> None:
        sources = {
            "categories": [
                {"id": "A", "tasks": [{"id": "A1", "phase": 8}]},
                {"id": "B", "tasks": [{"id": "B1", "phase": 10}]},
            ]
        }
        query = Query(
            select=Select(
                items=[
                    SelectItem(item="id", as_name="id"),
                    SelectItem(item="phase", as_name="phase"),
                ]
            ),
            from_clause=From(path=["categories", "tasks"]),
            grouped=None,
        )
        assert list(query.apply([sources])) == [
            {"id": "A1", "phase": 8},
            {"id": "B1", "phase": 10},
        ]
