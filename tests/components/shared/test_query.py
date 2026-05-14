"""Tests for Query DSL — object model and evaluation."""

import dataclasses

import pytest
from ruamel.yaml import YAML

from another_mood.components.shared.query import (
    From,
    Grouped,
    Query,
    Select,
    SelectItem,
    flatten_children,
    parse_query,
)
from another_mood.components.shared import data_catalog as dc


def _catalog(yaml_text: str) -> list[dc.Entity]:
    """Parse a YAML list of entity dicts into a flat Entity catalog."""
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
        assert list(From(path="entities").apply([sources])) == [
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
        assert list(From(path="categories.tasks").apply([sources])) == [
            {"id": "A1"},
            {"id": "A2"},
            {"id": "B1"},
        ]


class TestSelectItem:
    def test_extracts_field(self) -> None:
        assert SelectItem(item="name", as_="name").apply({"name": "Alice"}) == (
            "name",
            "Alice",
        )

    def test_renames_field(self) -> None:
        assert SelectItem(item="category", as_="id").apply(
            {"category": "user-management"}
        ) == ("id", "user-management")

    def test_raises_on_missing_field(self) -> None:
        with pytest.raises(KeyError):
            SelectItem(item="missing", as_="x").apply({"name": "Alice"})


class TestSelect:
    def test_projects_fields(self) -> None:
        select = Select(
            items=[
                SelectItem(item="category", as_="id"),
                SelectItem(item="category", as_="category"),
            ]
        )
        records = [{"category": "a", "extra": 1}, {"category": "b", "extra": 2}]
        assert list(select.apply(records)) == [
            {"id": "a", "category": "a"},
            {"id": "b", "category": "b"},
        ]

    def test_empty_records(self) -> None:
        select = Select(items=[SelectItem(item="x", as_="x")])
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
        assert list(Grouped(by="category", as_="entities").apply(records)) == expected

    def test_preserves_insertion_order(self) -> None:
        records = [
            {"id": "1", "cat": "b"},
            {"id": "2", "cat": "a"},
            {"id": "3", "cat": "b"},
        ]
        result = Grouped(by="cat", as_="items").apply(records)
        assert [r["cat"] for r in result] == ["b", "a"]

    def test_raises_on_missing_key(self) -> None:
        with pytest.raises(KeyError):
            Grouped(by="missing", as_="items").apply([{"id": "x"}])


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
                    SelectItem(item="category", as_="id"),
                    SelectItem(item="category", as_="category"),
                    SelectItem(item="entities", as_="entities"),
                ]
            ),
            from_=From(path="entities"),
            grouped=Grouped(by="category", as_="entities"),
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
            select=Select(items=[SelectItem(item="name", as_="name")]),
            from_=From(path="items"),
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
                    SelectItem(item="id", as_="id"),
                    SelectItem(item="phase", as_="phase"),
                ]
            ),
            from_=From(path="categories.tasks"),
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
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path="categories.tasks").derive(root)
        assert dc.flatten_tree(leaf, "tasks") == _catalog(
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

    def test_resolves_dotted_edge_name_as_single_step(self) -> None:
        """A catalog edge whose name itself contains a dot (e.g. from a
        singleton-object flattening) is consumed as one step by
        longest-match walk — naive ``path.split('.')`` would split it
        spuriously and miss the edge."""
        root = dc.build_tree(
            _catalog(
                """
                - id: members
                  item_type:
                    id: members.item
                    attributes:
                      - { id: hobby, type: object, required: false }
                      - id: hobby.pets
                        type: object[]
                        required: false
                        entity: members.hobby.pets
                        item_type: members.item.hobby.pets.item
                - id: members.hobby.pets
                  item_type:
                    id: members.item.hobby.pets.item
                    attributes:
                      - { id: id, type: string, required: true }
                  parent_entity: members
                """
            )
        )
        target = root.child("members").child("hobby.pets")
        assert From(path="members.hobby.pets").derive(root) is target


class TestGroupedDerive:
    def test_wraps_with_by_and_alias(self) -> None:
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path="categories.tasks").derive(root)
        wrapped = Grouped(by="phase", as_="tasks").derive(leaf)
        assert dc.flatten_tree(wrapped, "groups") == _catalog(
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


class TestGroupedDottedBy:
    """A dotted ``by`` must agree between derive and apply.

    Same shape as :class:`TestSelectItemDottedItem`: a flat dotted-name
    catalog edge lets ``Grouped.derive`` resolve ``by="a.b"`` by
    literal match, so ``apply`` must navigate the dotted path into
    each nested record rather than look up the literal ``"a.b"`` key.
    """

    _CATALOG = dc.Node(
        children=[
            (dc.Edge(name="a.b", type="string", required=True), dc.Node()),
        ],
    )

    def test_derive_resolves_flat_dotted_edge(self) -> None:
        result = Grouped(by="a.b", as_="items").derive(self._CATALOG)
        assert [edge.name for edge, _ in result.children] == ["a.b", "items"]

    def test_apply_traverses_nested_record(self) -> None:
        records = [
            {"a": {"b": "v1"}},
            {"a": {"b": "v2"}},
            {"a": {"b": "v1"}},
        ]
        expected = [
            {"a.b": "v1", "items": [{"a": {"b": "v1"}}, {"a": {"b": "v1"}}]},
            {"a.b": "v2", "items": [{"a": {"b": "v2"}}]},
        ]
        assert list(Grouped(by="a.b", as_="items").apply(records)) == expected


class TestSelectItemDottedItem:
    """A dotted ``item`` must agree between derive and apply.

    A catalog whose edge name is literally ``a.b`` (as singleton-object
    flattening produces) makes ``derive`` accept ``SelectItem(item="a.b")``
    by literal match.  ``apply`` should then navigate the dotted path
    into the nested record, not look up the literal ``"a.b"`` key —
    otherwise a query that derives cleanly fails at evaluation time.
    """

    _CATALOG = dc.Node(
        children=[
            (dc.Edge(name="a.b", type="string", required=True), dc.Node()),
        ],
    )

    def test_derive_resolves_flat_dotted_edge(self) -> None:
        edge, _ = SelectItem(item="a.b", as_="x").derive(self._CATALOG)
        assert edge.name == "x"
        assert edge.type == "string"

    def test_apply_traverses_nested_record(self) -> None:
        assert SelectItem(item="a.b", as_="x").apply({"a": {"b": "v"}}) == ("x", "v")


class TestSelectDerive:
    def test_projects_and_renames(self) -> None:
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        leaf = From(path="categories.tasks").derive(root)
        projected = Select(
            items=[
                SelectItem(item="phase", as_="id"),
                SelectItem(item="title", as_="title"),
            ]
        ).derive(leaf)
        assert dc.flatten_tree(projected, "projection") == _catalog(
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
            from_=From(path="categories.tasks"),
            grouped=Grouped(by="phase", as_="tasks"),
            select=Select(
                items=[
                    SelectItem(item="phase", as_="id"),
                    SelectItem(item="phase", as_="phase"),
                    SelectItem(item="tasks", as_="tasks"),
                ]
            ),
        )
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        result = dc.flatten_tree(query.derive(root), "tasks_by_phase")
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
            from_=From(path="categories.tasks"),
            grouped=None,
            select=Select(
                items=[
                    SelectItem(item="id", as_="id"),
                    SelectItem(item="title", as_="title"),
                ]
            ),
        )
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        result = dc.flatten_tree(query.derive(root), "task_titles")
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
                    SelectItem(item="category", as_="id"),
                    SelectItem(item="category", as_="category"),
                ]
            ),
            from_=From(path="entities"),
            grouped=Grouped(by="category", as_="items"),
        )

    def test_grouped_as_defaults_to_last_path_segment(self) -> None:
        raw = {
            "from": "entities",
            "grouped": {"by": "category"},
            "select": [{"item": "category"}],
        }
        assert parse_query(raw).grouped == Grouped(by="category", as_="entities")

    def test_from_dot_notation_splits_into_path(self) -> None:
        raw = {"from": "categories.tasks", "select": [{"item": "id"}]}
        assert parse_query(raw).from_ == From(path="categories.tasks")

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
            items=[SelectItem(item="name", as_="name")]
        )


def _catalog_name(field_name: str) -> str:
    """Translate a dataclass field name into its catalog edge name.

    DSL dataclasses use PEP 8 trailing underscores to dodge Python
    keyword conflicts (``from_`` / ``as_``); the catalog edge names use
    the bare YAML keys (``from`` / ``as``). Stripping the trailing
    underscore is the full translation.
    """
    return field_name.removesuffix("_")


class TestCatalogDriftSuppression:
    """Assert Query / Grouped / SelectItem ``catalog`` Nodes stay in sync.

    The catalog edge names use bare YAML keys, while the dataclasses use
    PEP 8 trailing-underscore names where the YAML key collides with a
    Python keyword. :func:`_catalog_name` bridges the two.

    ``id`` on a query record is synthesized by ``parse_query`` from the
    dict-pattern key and has no Query dataclass field — the test
    includes it explicitly in the expected set.
    """

    def test_query_top_level_edges_match_dataclass_fields(self) -> None:
        non_dotted = {
            edge.name for edge, _ in Query.catalog.children if "." not in edge.name
        }
        assert non_dotted == {"id"} | {
            _catalog_name(f.name) for f in dataclasses.fields(Query)
        }

    def test_grouped_dotted_edges_match_dataclass_fields(self) -> None:
        dotted = {
            edge.name.removeprefix("grouped.")
            for edge, _ in Query.catalog.children
            if edge.name.startswith("grouped.")
        }
        assert dotted == {_catalog_name(f.name) for f in dataclasses.fields(Grouped)}

    def test_select_item_edges_match_dataclass_fields(self) -> None:
        assert {edge.name for edge, _ in SelectItem.catalog.children} == {
            _catalog_name(f.name) for f in dataclasses.fields(SelectItem)
        }
