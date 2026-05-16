"""Tests for Query DSL — object model and evaluation."""

import dataclasses

import pytest
from ruamel.yaml import YAML

from another_mood.components.shared.query import (
    Direction,
    Flatten,
    From,
    Grouped,
    Missing,
    Query,
    QueryDeriveError,
    Select,
    SelectItem,
    Sort,
    Where,
    parse_flatten,
    parse_query,
)
from another_mood.components.shared.record_predicate import (
    FieldPredicate,
    Operator,
)
from another_mood.components.shared import data_catalog as dc


def _catalog(yaml_text: str) -> list[dc.Entity]:
    """Parse a YAML list of entity dicts into a flat Entity catalog."""
    loaded: list[dict[str, object]] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return [dc.Entity.from_dict(e) for e in loaded]


class TestFrom:
    def test_returns_rows_of_named_top_level_entity(self) -> None:
        sources = {"entities": [{"id": "user"}, {"id": "role"}]}
        assert list(From(name="entities").apply([sources])) == [
            {"id": "user"},
            {"id": "role"},
        ]

    def test_resolves_dotted_entity_id(self) -> None:
        sources = {"__definition": {"entities": [{"id": "user"}, {"id": "role"}]}}
        assert list(From(name="__definition.entities").apply([sources])) == [
            {"id": "user"},
            {"id": "role"},
        ]

    def test_raises_on_unknown_name(self) -> None:
        with pytest.raises(KeyError):
            From(name="missing").apply([{"members": []}])


_TOP_LEVEL_TASKS_CATALOG_YAML = """
- id: tasks
  item_type:
    id: tasks.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: title, type: string, required: true }
      - { id: phase, type: integer, required: true }
"""


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


class TestFlatten:
    def test_unwinds_array_attribute(self) -> None:
        flat = Flatten(of="tasks", as_="tasks")
        records = [
            {"id": 1, "name": "A", "tasks": [{"t": 1}, {"t": 2}]},
            {"id": 2, "name": "B", "tasks": [{"t": 3}]},
        ]
        assert list(flat.apply(records)) == [
            {"id": 1, "name": "A", "tasks": {"t": 1}},
            {"id": 1, "name": "A", "tasks": {"t": 2}},
            {"id": 2, "name": "B", "tasks": {"t": 3}},
        ]

    def test_renames_to_as(self) -> None:
        flat = Flatten(of="tasks", as_="task")
        records = [{"id": 1, "tasks": [{"t": 1}]}]
        assert list(flat.apply(records)) == [{"id": 1, "task": {"t": 1}}]

    def test_drops_empty_parents_by_default(self) -> None:
        flat = Flatten(of="tasks", as_="task")
        records: list[dict[str, object]] = [
            {"id": 1, "tasks": [{"t": 1}]},
            {"id": 2, "tasks": []},
        ]
        assert list(flat.apply(records)) == [{"id": 1, "task": {"t": 1}}]

    def test_preserve_empty_keeps_parent_without_as_field(self) -> None:
        flat = Flatten(of="tasks", as_="task", preserve_empty=True)
        records: list[dict[str, object]] = [
            {"id": 1, "tasks": [{"t": 1}]},
            {"id": 2, "tasks": []},
        ]
        assert list(flat.apply(records)) == [
            {"id": 1, "task": {"t": 1}},
            {"id": 2},
        ]

    def test_missing_key_treated_as_empty(self) -> None:
        flat = Flatten(of="tasks", as_="task", preserve_empty=True)
        # Optional array attribute omitted from a record behaves the same
        # as an explicit empty list.
        records = [{"id": 1}]
        assert list(flat.apply(records)) == [{"id": 1}]

    def test_unwinds_scalar_array(self) -> None:
        flat = Flatten(of="hobbies", as_="hobby")
        records = [{"id": 1, "hobbies": ["a", "b"]}]
        assert list(flat.apply(records)) == [
            {"id": 1, "hobby": "a"},
            {"id": 1, "hobby": "b"},
        ]


_FLATTEN_CATALOG_YAML = """
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
      - { id: phase, type: integer, required: true }
  parent_entity: categories
"""


class TestFlattenDerive:
    @pytest.fixture
    def categories(self) -> dc.Node:
        return dc.build_tree(_catalog(_FLATTEN_CATALOG_YAML)).child("categories")

    def test_replaces_array_edge_with_singleton(self, categories: dc.Node) -> None:
        leaf = Flatten(of="tasks", as_="task").derive(categories)
        edge_by_name = {e.name: e for e, _ in leaf.children}
        assert "tasks" not in edge_by_name
        assert edge_by_name["task"].type == "object"
        # preserve_empty=False → child rows always carry the namespace.
        assert edge_by_name["task"].required is True

    def test_preserve_empty_makes_as_field_optional(self, categories: dc.Node) -> None:
        leaf = Flatten(of="tasks", as_="task", preserve_empty=True).derive(categories)
        edge_by_name = {e.name: e for e, _ in leaf.children}
        assert edge_by_name["task"].required is False

    def test_keeps_as_same_as_of_when_omitted(self, categories: dc.Node) -> None:
        leaf = Flatten(of="tasks", as_="tasks").derive(categories)
        edge_by_name = {e.name: e for e, _ in leaf.children}
        assert "tasks" in edge_by_name
        # Type still drops the [] — same name, different cardinality.
        assert edge_by_name["tasks"].type == "object"

    def test_raises_on_unknown_attribute(self, categories: dc.Node) -> None:
        with pytest.raises(QueryDeriveError, match="missing"):
            Flatten(of="missing", as_="x").derive(categories)

    def test_raises_when_target_not_array(self, categories: dc.Node) -> None:
        with pytest.raises(QueryDeriveError, match="not an array"):
            Flatten(of="title", as_="x").derive(categories)

    def test_raises_on_as_collision(self, categories: dc.Node) -> None:
        with pytest.raises(QueryDeriveError, match="collides"):
            Flatten(of="tasks", as_="title").derive(categories)


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
            from_=From(name="entities"),
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
            from_=From(name="items"),
            grouped=None,
        )
        assert list(query.apply([sources])) == [{"name": "a"}, {"name": "b"}]


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
    def test_returns_named_top_level_entity(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        assert From(name="tasks").derive(root) is root.child("tasks")

    def test_accepts_dotted_top_level_id(self) -> None:
        root = dc.build_tree(
            _catalog(
                """
                - id: __definition.entities
                  item_type:
                    id: __definition.entities.item
                    attributes:
                      - { id: id, type: string, required: true }
                """
            )
        )
        assert From(name="__definition.entities").derive(root) is root.child(
            "__definition.entities"
        )

    def test_rejects_unknown_name(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="missing"):
            From(name="missing").derive(root)

    def test_rejects_composition_walk(self) -> None:
        # ``categories.tasks`` is a child entity, not a root edge —
        # composition descent is the job of ``flatten:``.
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="categories.tasks"):
            From(name="categories.tasks").derive(root)


class TestGroupedDerive:
    def test_wraps_with_by_and_alias(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
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


class TestSelectDerive:
    def test_projects_and_renames(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
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
            from_=From(name="tasks"),
            grouped=Grouped(by="phase", as_="tasks"),
            select=Select(
                items=[
                    SelectItem(item="phase", as_="id"),
                    SelectItem(item="phase", as_="phase"),
                    SelectItem(item="tasks", as_="tasks"),
                ]
            ),
        )
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
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
            from_=From(name="tasks"),
            grouped=None,
            select=Select(
                items=[
                    SelectItem(item="id", as_="id"),
                    SelectItem(item="title", as_="title"),
                ]
            ),
        )
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
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


class TestWhere:
    """Pipeline wrapper around a :class:`RecordPredicate`."""

    def test_apply_filters_records(self) -> None:
        where = Where(
            predicate=FieldPredicate(
                key_path="open", operator=Operator.EQ, target=True
            ),
        )
        records = [{"open": True}, {"open": False}, {"open": True}]
        assert list(where.apply(records)) == [{"open": True}, {"open": True}]

    def test_derive_returns_catalog_unchanged_for_valid_key_path(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
        where = Where(
            predicate=FieldPredicate(key_path="phase", operator=Operator.GT, target=5),
        )
        assert where.derive(leaf) is leaf

    def test_derive_translates_unknown_key_path(self) -> None:
        """The predicate-side :class:`UnknownKeyPathError` is
        converted to the user-facing :class:`QueryDeriveError` at the
        clause boundary so diagnostics carry source provenance."""
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
        where = Where(
            predicate=FieldPredicate(
                key_path="nonexistent", operator=Operator.EQ, target=1
            ),
        )
        with pytest.raises(QueryDeriveError, match="nonexistent"):
            where.derive(leaf)


class TestSort:
    """Sort orders records by one attribute; ``direction`` × ``missing``
    are orthogonal so the default ``missing=last`` invariant holds for
    both ``asc`` and ``desc``."""

    @pytest.mark.parametrize(
        ("direction", "missing", "expected"),
        [
            (Direction.ASC, Missing.LAST, [{"x": 1}, {"x": 2}, {}]),
            (Direction.DESC, Missing.LAST, [{"x": 2}, {"x": 1}, {}]),
            (Direction.ASC, Missing.FIRST, [{}, {"x": 1}, {"x": 2}]),
            (Direction.DESC, Missing.FIRST, [{}, {"x": 2}, {"x": 1}]),
        ],
    )
    def test_direction_missing_matrix(
        self,
        direction: Direction,
        missing: Missing,
        expected: list[dict[str, object]],
    ) -> None:
        records = [{"x": 2}, {}, {"x": 1}]
        assert (
            list(Sort(by="x", direction=direction, missing=missing).apply(records))
            == expected
        )

    def test_stable_for_equal_keys(self) -> None:
        # Python ``sorted`` is stable; the original order of equal keys
        # is preserved so subsequent sort + group / sort combinations
        # behave predictably.
        records = [
            {"x": 1, "tag": "a"},
            {"x": 1, "tag": "b"},
            {"x": 1, "tag": "c"},
        ]
        assert list(Sort(by="x").apply(records)) == records

    def test_empty_records(self) -> None:
        assert list(Sort(by="x").apply([])) == []

    def test_dotted_by_path(self) -> None:
        # ``pluck`` resolves dotted paths; sort inherits that.
        records = [
            {"meta": {"phase": 12}},
            {"meta": {"phase": 8}},
            {"meta": {"phase": 10}},
        ]
        assert list(Sort(by="meta.phase").apply(records)) == [
            {"meta": {"phase": 8}},
            {"meta": {"phase": 10}},
            {"meta": {"phase": 12}},
        ]


class TestSortDerive:
    def test_returns_catalog_unchanged_for_valid_by(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
        assert Sort(by="phase").derive(leaf) is leaf

    def test_raises_on_unknown_by(self) -> None:
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
        with pytest.raises(QueryDeriveError, match="nonexistent"):
            Sort(by="nonexistent").derive(leaf)

    def test_raises_on_by_path_crossing_array(self) -> None:
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="tasks.title"):
            Sort(by="tasks.title").derive(root.child("categories"))


class TestQueryPipelineOrder:
    def test_where_filters_before_grouped(self) -> None:
        """``from → where → grouped → select``: where prunes records
        before grouping so empty groups never form."""
        sources = {
            "items": [
                {"id": "a", "cat": "x", "open": True},
                {"id": "b", "cat": "x", "open": False},
                {"id": "c", "cat": "y", "open": False},
            ]
        }
        query = parse_query(
            YAML(typ="safe").load(  # type: ignore[no-untyped-call]
                """
                from: items
                where:
                  open: true
                grouped:
                  by: cat
                  as: items
                select:
                  - item: cat
                  - item: items
                """
            )
        )
        assert list(query.apply([sources])) == [
            {"cat": "x", "items": [{"id": "a", "cat": "x", "open": True}]}
        ]

    def test_sort_runs_after_select(self) -> None:
        """``sort`` sees the projected output (matches SQL ``ORDER BY``
        after ``SELECT``), so ``by:`` can reference a ``select`` alias."""
        sources = {
            "items": [
                {"name": "a", "phase": 3},
                {"name": "b", "phase": 1},
                {"name": "c", "phase": 2},
            ]
        }
        query = parse_query(
            YAML(typ="safe").load(  # type: ignore[no-untyped-call]
                """
                from: items
                select:
                  - item: name
                  - item: phase
                    as: rank
                sort:
                  by: rank
                """
            )
        )
        assert list(query.apply([sources])) == [
            {"name": "b", "rank": 1},
            {"name": "c", "rank": 2},
            {"name": "a", "rank": 3},
        ]

    def test_flatten_runs_between_from_and_where(self) -> None:
        """``flatten`` unwinds before ``where``, so the predicate sees the
        post-flatten row shape (parent fields top-level, child namespace
        scoped under ``as:``)."""
        sources = {
            "categories": [
                {
                    "id": "A",
                    "tasks": [{"id": "A1", "phase": 8}, {"id": "A2", "phase": 10}],
                },
                {
                    "id": "B",
                    "tasks": [{"id": "B1", "phase": 10}],
                },
            ]
        }
        query = parse_query(
            YAML(typ="safe").load(  # type: ignore[no-untyped-call]
                """
                from: categories
                flatten:
                  of: tasks
                  as: task
                select:
                  - item: id
                    as: category_id
                  - item: task
                """
            )
        )
        assert list(query.apply([sources])) == [
            {"category_id": "A", "task": {"id": "A1", "phase": 8}},
            {"category_id": "A", "task": {"id": "A2", "phase": 10}},
            {"category_id": "B", "task": {"id": "B1", "phase": 10}},
        ]

    def test_list_form_flattens_chain_sequentially(self) -> None:
        """Each later entry in the ``flatten:`` list sees the row shape
        produced by the earlier ones — the second unwind multiplies over
        the first."""
        sources = {"members": [{"id": 1, "hobbies": ["h1"], "pets": ["p1", "p2"]}]}
        query = parse_query(
            YAML(typ="safe").load(  # type: ignore[no-untyped-call]
                """
                from: members
                flatten:
                  - { of: hobbies, as: hobby }
                  - { of: pets, as: pet }
                select:
                  - item: id
                  - item: hobby
                  - item: pet
                """
            )
        )
        assert list(query.apply([sources])) == [
            {"id": 1, "hobby": "h1", "pet": "p1"},
            {"id": 1, "hobby": "h1", "pet": "p2"},
        ]

    def test_sort_after_grouped(self) -> None:
        """After grouping, ``sort`` orders the group records."""
        sources = {
            "items": [
                {"id": "a", "cat": "x"},
                {"id": "b", "cat": "z"},
                {"id": "c", "cat": "y"},
            ]
        }
        query = parse_query(
            YAML(typ="safe").load(  # type: ignore[no-untyped-call]
                """
                from: items
                grouped:
                  by: cat
                  as: items
                select:
                  - item: cat
                  - item: items
                sort:
                  by: cat
                """
            )
        )
        assert [row["cat"] for row in query.apply([sources])] == ["x", "y", "z"]


class TestQueryDeriveWithSort:
    def test_sort_validates_against_post_select_catalog(self) -> None:
        """``sort.derive`` runs after ``select.derive``, so ``by:`` must
        resolve in the projected catalog — sorting by a source attribute
        that ``select`` did not project raises ``QueryDeriveError``."""
        query = Query(
            from_=From(name="tasks"),
            grouped=None,
            select=Select(items=[SelectItem(item="title", as_="title")]),
            sort=Sort(by="phase"),
        )
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="phase"):
            query.derive(root)

    def test_sort_by_select_alias(self) -> None:
        """``sort.by`` resolves the ``as:`` alias produced by select."""
        query = Query(
            from_=From(name="tasks"),
            grouped=None,
            select=Select(
                items=[
                    SelectItem(item="phase", as_="rank"),
                    SelectItem(item="title", as_="title"),
                ]
            ),
            sort=Sort(by="rank"),
        )
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        result = dc.flatten_tree(query.derive(root), "ranked_tasks")
        assert result == _catalog(
            """
            - id: ranked_tasks
              item_type:
                id: ranked_tasks.item
                attributes:
                  - { id: rank, type: integer, required: true }
                  - { id: title, type: string, required: true }
            """
        )


class TestParseFlatten:
    def test_shorthand(self) -> None:
        assert list(parse_flatten("tasks")) == [Flatten(of="tasks", as_="tasks")]

    def test_object_form(self) -> None:
        assert list(
            parse_flatten({"of": "tasks", "as": "task", "preserve_empty": True})
        ) == [Flatten(of="tasks", as_="task", preserve_empty=True)]

    def test_object_form_as_defaults_to_of(self) -> None:
        assert list(parse_flatten({"of": "tasks"})) == [
            Flatten(of="tasks", as_="tasks")
        ]

    def test_list_form_mixes_shorthand_and_object(self) -> None:
        assert list(parse_flatten(["hobbies", {"of": "pets", "as": "pet"}])) == [
            Flatten(of="hobbies", as_="hobbies"),
            Flatten(of="pets", as_="pet"),
        ]

    def test_rejects_unsupported_shape(self) -> None:
        with pytest.raises(TypeError):
            parse_flatten(42)


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
            from_=From(name="entities"),
            grouped=Grouped(by="category", as_="items"),
            where=None,
        )

    def test_grouped_as_defaults_to_last_segment_of_from(self) -> None:
        raw = {
            "from": "__definition.entities",
            "grouped": {"by": "category"},
            "select": [{"item": "category"}],
        }
        assert parse_query(raw).grouped == Grouped(by="category", as_="entities")

    def test_from_dotted_id_is_carried_verbatim(self) -> None:
        raw = {"from": "__definition.entities", "select": [{"item": "id"}]}
        assert parse_query(raw).from_ == From(name="__definition.entities")

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

    def test_parses_where_wraps_in_where(self) -> None:
        """``parse_query`` wraps the parsed predicate in :class:`Where`;
        detailed AST shape per input is covered in
        ``test_record_predicate.TestParseRecordPredicate``."""
        raw = {
            "from": "items",
            "where": {"x": 1},
            "select": [{"item": "id"}],
        }
        assert parse_query(raw).where == Where(
            predicate=FieldPredicate(key_path="x", operator=Operator.EQ, target=1),
        )

    def test_parses_query_without_where(self) -> None:
        raw = {"from": "items", "select": [{"item": "id"}]}
        assert parse_query(raw).where is None

    def test_parses_sort_with_defaults(self) -> None:
        raw = {
            "from": "items",
            "select": [{"item": "name"}],
            "sort": {"by": "name"},
        }
        assert parse_query(raw).sort == Sort(
            by="name", direction=Direction.ASC, missing=Missing.LAST
        )

    def test_parses_query_without_flatten(self) -> None:
        raw = {"from": "items", "select": [{"item": "id"}]}
        assert list(parse_query(raw).flatten) == []

    def test_parses_flatten_wires_into_query(self) -> None:
        raw = {"from": "items", "flatten": "tasks", "select": [{"item": "id"}]}
        assert list(parse_query(raw).flatten) == [Flatten(of="tasks", as_="tasks")]

    def test_parses_sort_full(self) -> None:
        raw = {
            "from": "items",
            "select": [{"item": "name"}],
            "sort": {"by": "name", "direction": "desc", "missing": "first"},
        }
        assert parse_query(raw).sort == Sort(
            by="name", direction=Direction.DESC, missing=Missing.FIRST
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
    """Assert ``Query.catalog`` stays in sync with the Query dataclass.

    The catalog edge names use bare YAML keys, while the dataclasses use
    PEP 8 trailing-underscore names where the YAML key collides with a
    Python keyword. :func:`_catalog_name` bridges the two.

    ``id`` on a query record is synthesized by ``parse_query`` from the
    dict-pattern key and has no Query dataclass field — the test
    includes it explicitly in the expected set.
    """

    def test_query_edges_match_dataclass_fields(self) -> None:
        assert {edge.name for edge, _ in Query.catalog.children} == {"id"} | {
            _catalog_name(f.name) for f in dataclasses.fields(Query)
        }
