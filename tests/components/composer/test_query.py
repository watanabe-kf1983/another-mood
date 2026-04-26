"""Tests for Query DSL — object model and evaluation."""

import pytest
from ruamel.yaml import YAML

from another_mood.components.composer.catalog_node import CatalogNode
from another_mood.components.composer.query import (
    From,
    Grouped,
    Query,
    Select,
    SelectItem,
    flatten_children,
)
from another_mood.components.shared import data_catalog as dc


def _catalog(yaml_text: str) -> list[dc.Entity]:
    """Parse a YAML list of entity dicts into a flat dc.Entity catalog."""
    loaded: list[dict[str, object]] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return [dc.Entity.from_dict(e) for e in loaded]


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


_TASKS_CATALOG_YAML = """
- id: categories
  item_type:
    id: categories.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: title, type: string, required: true }
      - id: tasks
        type: object[]
        required: true
        entity: categories.tasks
        item_type: categories.item.tasks.item
- id: categories.tasks
  item_type:
    id: categories.item.tasks.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: title, type: string, required: true }
      - { id: phase, type: integer, required: true }
  parent_entity: categories
"""


class TestFromDerive:
    def test_walks_dot_path_to_leaf(self) -> None:
        root = CatalogNode.build_from_catalog(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path=["categories", "tasks"]).derive(root)
        assert leaf.to_catalog_list("tasks") == _catalog(
            """
            - id: tasks
              item_type:
                id: tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
                  - { id: phase, type: integer, required: true }
            """
        )


class TestGroupedDerive:
    def test_wraps_with_by_and_as_name(self) -> None:
        root = CatalogNode.build_from_catalog(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path=["categories", "tasks"]).derive(root)
        wrapped = Grouped(by="phase", as_name="tasks").derive(leaf)
        assert wrapped.to_catalog_list("groups") == _catalog(
            """
            - id: groups
              item_type:
                id: groups.item
                attributes:
                  - { id: phase, type: integer, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    entity: groups.tasks
                    item_type: groups.item.tasks.item
            - id: groups.tasks
              item_type:
                id: groups.item.tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: groups
            """
        )


class TestSelectDerive:
    def test_projects_and_renames(self) -> None:
        root = CatalogNode.build_from_catalog(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path=["categories", "tasks"]).derive(root)
        projected = Select(
            items=[
                SelectItem(item="phase", as_name="id"),
                SelectItem(item="title", as_name="title"),
            ]
        ).derive(leaf)
        assert projected.to_catalog_list("projection") == _catalog(
            """
            - id: projection
              item_type:
                id: projection.item
                attributes:
                  - { id: id, type: integer, required: true }
                  - { id: title, type: string, required: true }
            """
        )


class TestQueryDerive:
    def test_tasks_by_phase(self) -> None:
        """End-to-end: from → grouped → select → flatten produces the expected catalog."""
        query = Query(
            from_clause=From(path=["categories", "tasks"]),
            grouped=Grouped(by="phase", as_name="tasks"),
            select=Select(
                items=[
                    SelectItem(item="phase", as_name="id"),
                    SelectItem(item="phase", as_name="phase"),
                    SelectItem(item="tasks", as_name="tasks"),
                ]
            ),
        )
        root = CatalogNode.build_from_catalog(_catalog(_TASKS_CATALOG_YAML))
        result = query.derive(root).to_catalog_list("tasks_by_phase")
        assert result == _catalog(
            """
            - id: tasks_by_phase
              item_type:
                id: tasks_by_phase.item
                attributes:
                  - { id: id, type: integer, required: true }
                  - { id: phase, type: integer, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    entity: tasks_by_phase.tasks
                    item_type: tasks_by_phase.item.tasks.item
            - id: tasks_by_phase.tasks
              item_type:
                id: tasks_by_phase.item.tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: tasks_by_phase
            """
        )

    def test_without_grouped(self) -> None:
        query = Query(
            from_clause=From(path=["categories", "tasks"]),
            grouped=None,
            select=Select(
                items=[
                    SelectItem(item="id", as_name="id"),
                    SelectItem(item="title", as_name="title"),
                ]
            ),
        )
        root = CatalogNode.build_from_catalog(_catalog(_TASKS_CATALOG_YAML))
        result = query.derive(root).to_catalog_list("task_titles")
        assert result == _catalog(
            """
            - id: task_titles
              item_type:
                id: task_titles.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
            """
        )
