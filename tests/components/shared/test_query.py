"""Tests for Query DSL — object model and evaluation."""

import dataclasses

import pytest
from ruamel.yaml import YAML

from another_mood.components.preprocess.query_normalizer import normalize_query
from another_mood.components.shared.query import (
    Direction,
    Flatten,
    From,
    Grouped,
    Join,
    Merge,
    Missing,
    PassThrough,
    Query,
    QueryDeriveError,
    Select,
    SelectItem,
    Sort,
    Where,
    evaluation_order,
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


def _parse_query_yaml(yaml_text: str) -> Query:
    """Load YAML, normalize, and parse — mirrors the production path
    where ``query_deriver`` runs ``normalize_query`` before
    ``Query.from_dict`` sees the record.
    """
    raw: dict[str, object] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return Query.from_dict(normalize_query({"id": "q", **raw}))


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
        child_entity: categories.tasks
        child_item_type: categories.item.tasks.item
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
        with pytest.raises(QueryDeriveError, match="unknown source 'missing'"):
            From(name="missing").derive(root)

    def test_rejects_composition_walk(self) -> None:
        # ``categories.tasks`` is a child entity, not a root edge —
        # composition descent is the job of ``flatten:``.
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="categories.tasks"):
            From(name="categories.tasks").derive(root)


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
        child_entity: categories.tasks
        child_item_type: categories.item.tasks.item
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
        # Catalog-layer error here; Query.derive translates it into
        # QueryDeriveError at the pipeline boundary.
        with pytest.raises(dc.UnknownChildError, match="missing"):
            Flatten(of="missing", as_="x").derive(categories)

    def test_raises_when_target_not_array(self, categories: dc.Node) -> None:
        with pytest.raises(QueryDeriveError, match="not an array"):
            Flatten(of="title", as_="x").derive(categories)

    def test_raises_on_as_collision(self, categories: dc.Node) -> None:
        with pytest.raises(QueryDeriveError, match="collides"):
            Flatten(of="tasks", as_="title").derive(categories)


class TestFlattenFromDict:
    def test_lifts_canonical_mapping(self) -> None:
        assert Flatten.from_dict(
            {"of": "tasks", "as": "task", "preserve_empty": True}
        ) == Flatten(of="tasks", as_="task", preserve_empty=True)


_CATS_TASKS_CATALOG_YAML = """
- id: cats
  item_type:
    id: cats.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: name, type: string, required: true }
- id: tasks
  item_type:
    id: tasks.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: title, type: string, required: true }
      - { id: cat, type: string, required: true }
"""


class TestMerge:
    """``Merge.apply``: nested attach with default cardinality.

    Every left row survives; matching right rows arrive as a list under
    ``as_`` (possibly empty). Unwinding that list is the role of
    ``Join.flatten`` (applied by ``Query.apply`` right after the merge).
    """

    def test_attaches_matched_right_rows_under_as_(self) -> None:
        merge = Merge(on_left="id", on_right="cat", right_as="tasks")
        left = [{"id": "A"}, {"id": "B"}]
        right = [
            {"id": "A1", "cat": "A"},
            {"id": "A2", "cat": "A"},
            {"id": "B1", "cat": "B"},
        ]
        assert list(merge.apply(left, right)) == [
            {
                "id": "A",
                "tasks": [
                    {"id": "A1", "cat": "A"},
                    {"id": "A2", "cat": "A"},
                ],
            },
            {"id": "B", "tasks": [{"id": "B1", "cat": "B"}]},
        ]

    def test_left_row_with_no_match_gets_empty_list(self) -> None:
        merge = Merge(on_left="id", on_right="cat", right_as="tasks")
        left = [{"id": "A"}, {"id": "Z"}]
        right = [{"id": "A1", "cat": "A"}]
        assert list(merge.apply(left, right)) == [
            {"id": "A", "tasks": [{"id": "A1", "cat": "A"}]},
            {"id": "Z", "tasks": []},
        ]

    def test_left_row_missing_key_gets_empty_list(self) -> None:
        # Schema validation in ``Merge.derive`` rules out unknown
        # ``on.left``, but optional attributes can still be absent on
        # individual rows — those rows behave like a no-match.
        merge = Merge(on_left="id", on_right="cat", right_as="tasks")
        left: list[dict[str, object]] = [{}]
        right = [{"id": "A1", "cat": "A"}]
        assert list(merge.apply(left, right)) == [{"tasks": []}]

    def test_right_row_missing_key_excluded_from_index(self) -> None:
        merge = Merge(on_left="id", on_right="cat", right_as="tasks")
        left = [{"id": "A"}]
        right = [{"id": "A1", "cat": "A"}, {"id": "stray"}]
        assert list(merge.apply(left, right)) == [
            {"id": "A", "tasks": [{"id": "A1", "cat": "A"}]},
        ]

    def test_dotted_left_path(self) -> None:
        # ``pluck`` resolves dotted paths on the left row.
        merge = Merge(on_left="meta.cat", on_right="cat", right_as="tasks")
        left = [{"meta": {"cat": "A"}}]
        right = [{"id": "A1", "cat": "A"}]
        assert list(merge.apply(left, right)) == [
            {"meta": {"cat": "A"}, "tasks": [{"id": "A1", "cat": "A"}]},
        ]


class TestMergeDerive:
    """``Merge.derive``: schema-side merge.  ``require_child`` runs on
    both sides, so the asymmetry rule (no array crossings) and the
    ``as_`` collision rule are enforced before any data is touched."""

    @pytest.fixture
    def root(self) -> dc.Node:
        return dc.build_tree(_catalog(_CATS_TASKS_CATALOG_YAML))

    def test_attaches_right_node_under_as_edge(self, root: dc.Node) -> None:
        merge = Merge(on_left="id", on_right="cat", right_as="tasks")
        left = root.child("cats")
        right = root.child("tasks")
        merged = merge.derive(left, right)
        edge_by_name = {e.name: (e, n) for e, n in merged.children}
        # Left attrs preserved.
        assert {"id", "name"}.issubset(edge_by_name)
        # Right surfaces as an object[] under as_.
        edge, node = edge_by_name["tasks"]
        assert edge.type == "object[]"
        assert edge.required is True
        assert node is right

    def test_raises_when_left_key_unknown(self, root: dc.Node) -> None:
        merge = Merge(on_left="missing", on_right="cat", right_as="tasks")
        with pytest.raises(dc.UnknownChildError, match="missing"):
            merge.derive(root.child("cats"), root.child("tasks"))

    def test_raises_when_right_key_unknown(self, root: dc.Node) -> None:
        merge = Merge(on_left="id", on_right="missing", right_as="tasks")
        with pytest.raises(dc.UnknownChildError, match="missing"):
            merge.derive(root.child("cats"), root.child("tasks"))

    def test_raises_on_as_collision(self, root: dc.Node) -> None:
        # ``right_as="name"`` already exists as an attribute on cats.
        merge = Merge(on_left="id", on_right="cat", right_as="name")
        with pytest.raises(QueryDeriveError, match="collides"):
            merge.derive(root.child("cats"), root.child("tasks"))

    def test_raises_when_left_key_crosses_array(self) -> None:
        # Asymmetry rule: ``on.left`` cannot reach inside a nested array.
        # The flattened catalog encoding has no direct edge ``tasks.title``
        # under categories, so ``require_child`` raises.
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        merge = Merge(on_left="tasks.title", on_right="id", right_as="x")
        with pytest.raises(dc.UnknownChildError, match="tasks.title"):
            merge.derive(root.child("categories"), root.child("categories"))


class TestJoin:
    """Composition of right sub-Query, ``Merge``, and optional
    ``Flatten``. Each part is covered by its own test class."""

    def test_apply_chains_right_then_merge_then_flatten(self) -> None:
        sources = {
            "cats": [{"id": "A"}, {"id": "B"}],
            "tasks": [
                {"id": "A1", "cat": "A"},
                {"id": "A2", "cat": "A"},
                {"id": "B1", "cat": "B"},
            ],
        }
        join = Join(
            right=Query(from_=From(name="tasks")),
            merge=Merge(on_left="id", on_right="cat", right_as="tasks"),
            flatten=Flatten(of="tasks", as_="task"),
        )
        left = [{"id": "A"}, {"id": "B"}]
        assert list(join.apply(left, [sources])) == [
            {"id": "A", "task": {"id": "A1", "cat": "A"}},
            {"id": "A", "task": {"id": "A2", "cat": "A"}},
            {"id": "B", "task": {"id": "B1", "cat": "B"}},
        ]

    def test_derive_chains_right_then_merge_then_flatten(self) -> None:
        root = dc.build_tree(_catalog(_CATS_TASKS_CATALOG_YAML))
        join = Join(
            right=Query(from_=From(name="tasks")),
            merge=Merge(on_left="id", on_right="cat", right_as="tasks"),
            flatten=Flatten(of="tasks", as_="task"),
        )
        attrs = {e.name: e for e, _ in join.derive(root.child("cats"), root).children}
        # Merge's ``tasks`` edge has been unwound by Flatten — only the
        # singleton ``task`` namespace remains, with inlined siblings.
        assert "tasks" not in attrs
        assert attrs["task"].type == "object"
        assert "task.id" in attrs


class TestJoinFromDict:
    def test_basic(self) -> None:
        assert Join.from_dict(
            {"to": "tasks", "on": {"left": "id", "right": "cat"}, "as": "tasks"}
        ) == Join(
            right=Query(from_=From(name="tasks")),
            merge=Merge(on_left="id", on_right="cat", right_as="tasks"),
        )

    def test_without_where_leaves_right_subquery_passthrough(self) -> None:
        join = Join.from_dict(
            {"to": "tasks", "on": {"left": "id", "right": "cat"}, "as": "tasks"}
        )
        assert join.right.where == PassThrough()

    def test_without_flatten_leaves_join_flatten_none(self) -> None:
        join = Join.from_dict(
            {"to": "tasks", "on": {"left": "id", "right": "cat"}, "as": "tasks"}
        )
        assert join.flatten is None

    def test_wires_inline_flatten(self) -> None:
        join = Join.from_dict(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "tasks",
                "flatten": {"of": "tasks", "as": "task", "preserve_empty": True},
            }
        )
        assert join.flatten == Flatten(of="tasks", as_="task", preserve_empty=True)

    def test_wires_pre_join_where(self) -> None:
        """``join[].where:`` becomes the right sub-Query's ``where``;
        no special handling on ``Join`` itself."""
        join = Join.from_dict(
            {
                "to": "tasks",
                "on": {"left": "id", "right": "cat"},
                "as": "tasks",
                "where": {"open": True},
            }
        )
        assert join.right.where == Where(
            predicate=FieldPredicate(
                key_path="open", operator=Operator.EQ, target=True
            ),
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

    def test_derive_propagates_unknown_key_path(self) -> None:
        """Predicate-side misses surface as the catalog-layer
        :class:`dc.UnknownChildError`; ``Query.derive`` translates it
        into a user-facing :class:`QueryDeriveError` at the pipeline
        boundary."""
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        leaf = From(name="tasks").derive(root)
        where = Where(
            predicate=FieldPredicate(
                key_path="nonexistent", operator=Operator.EQ, target=1
            ),
        )
        with pytest.raises(dc.UnknownChildError, match="nonexistent"):
            where.derive(leaf)


class TestWhereFromDict:
    def test_wraps_parsed_predicate(self) -> None:
        """``Where.from_dict`` delegates the predicate AST construction
        to :func:`parse_record_predicate`; detailed AST shape per input
        is covered in ``test_record_predicate.TestParseRecordPredicate``."""
        assert Where.from_dict({"x": 1}) == Where(
            predicate=FieldPredicate(key_path="x", operator=Operator.EQ, target=1),
        )


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
                origin_item_type: groups.item
                attributes:
                  - { id: phase, type: integer, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    child_entity: groups.tasks
                    child_item_type: groups.item.tasks.item
            - id: groups.tasks
              item_type:
                id: groups.item.tasks.item
                origin_item_type: tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: groups
            """
        )


class TestSelectItem:
    def test_extracts_field(self) -> None:
        assert SelectItem(item="name", as_="name").apply({"name": "Alice"}) == {
            "name": "Alice",
        }

    def test_renames_field(self) -> None:
        assert SelectItem(item="category", as_="id").apply(
            {"category": "user-management"}
        ) == {"id": "user-management"}

    def test_returns_empty_for_missing_field(self) -> None:
        # The JSON data model treats a nullable field as an absent key,
        # so projecting an optional schema attribute on a record that
        # happens to omit it yields no output entry rather than raising.
        assert SelectItem(item="missing", as_="x").apply({"name": "Alice"}) == {}


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

    def test_optional_field_absent_in_some_records(self) -> None:
        # A schema-optional attribute (here ``parent_entity``) is absent
        # on some records and present on others.  ``select`` must
        # produce variable-shape rows that omit the key when missing.
        select = Select(
            items=[
                SelectItem(item="id", as_="id"),
                SelectItem(item="parent_entity", as_="parent_entity"),
            ]
        )
        records = [
            {"id": "root_a"},
            {"id": "child_a", "parent_entity": "root_a"},
        ]
        assert list(select.apply(records)) == [
            {"id": "root_a"},
            {"id": "child_a", "parent_entity": "root_a"},
        ]


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


class TestSelectFromDict:
    def test_lifts_items(self) -> None:
        assert Select.from_dict(
            [{"item": "category", "as": "id"}, {"item": "category", "as": "category"}]
        ) == Select(
            items=[
                SelectItem(item="category", as_="id"),
                SelectItem(item="category", as_="category"),
            ]
        )


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
        with pytest.raises(dc.UnknownChildError, match="nonexistent"):
            Sort(by="nonexistent").derive(leaf)

    def test_raises_on_by_path_crossing_array(self) -> None:
        root = dc.build_tree(_catalog(_TASKS_CATALOG_YAML))
        with pytest.raises(dc.UnknownChildError, match="tasks.title"):
            Sort(by="tasks.title").derive(root.child("categories"))


class TestQueryPipeline:
    """Assert that Query runs clauses in the order
    ``from → flatten* → join* → where? → grouped? → select → sort?``.

    Each test pins one user-visible promise that depends on the ordering.
    Only adjacent pairs are tested; non-adjacent pairs (flatten<grouped,
    flatten<select, ...) follow by transitivity because ``Query.apply``
    runs a single fixed order.
    """

    def test_apply_where_after_flatten(self) -> None:
        """``where`` sees the post-flatten row shape and can reference
        child fields under the ``as_`` namespace.  If the order were
        reversed, ``task.phase`` would not resolve while ``tasks`` is
        still an array."""
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
        query = _parse_query_yaml(
            """
                from: categories
                flatten:
                  of: tasks
                  as: task
                where:
                  task.phase: 10
                select:
                  - item: id
                    as: category_id
                  - item: task
                """
        )
        assert list(query.apply([sources])) == [
            {"category_id": "A", "task": {"id": "A2", "phase": 10}},
            {"category_id": "B", "task": {"id": "B1", "phase": 10}},
        ]

    def test_apply_grouped_after_where(self) -> None:
        """Rows pruned by ``where`` do not enter any group, so no empty
        group ever forms."""
        sources = {
            "items": [
                {"id": "a", "cat": "x", "open": True},
                {"id": "b", "cat": "x", "open": False},
                {"id": "c", "cat": "y", "open": False},
            ]
        }
        query = _parse_query_yaml(
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
        assert list(query.apply([sources])) == [
            {"cat": "x", "items": [{"id": "a", "cat": "x", "open": True}]}
        ]

    def test_apply_select_after_grouped(self) -> None:
        """``select`` can project ``grouped``'s ``as_`` (the group
        payload).  If the order were reversed, ``members`` would not
        exist on the record and ``select`` would raise ``KeyError``."""
        sources = {
            "items": [
                {"id": "a", "cat": "x"},
                {"id": "b", "cat": "x"},
                {"id": "c", "cat": "y"},
            ]
        }
        query = _parse_query_yaml(
            """
                from: items
                grouped:
                  by: cat
                  as: members
                select:
                  - item: cat
                  - item: members
                """
        )
        assert list(query.apply([sources])) == [
            {
                "cat": "x",
                "members": [{"id": "a", "cat": "x"}, {"id": "b", "cat": "x"}],
            },
            {"cat": "y", "members": [{"id": "c", "cat": "y"}]},
        ]

    def test_apply_sort_after_select(self) -> None:
        """``sort.by`` resolves the ``as:`` alias produced by ``select``
        (data side).  If the order were reversed, the alias would not
        exist on the record."""
        sources = {
            "items": [
                {"name": "a", "phase": 3},
                {"name": "b", "phase": 1},
                {"name": "c", "phase": 2},
            ]
        }
        query = _parse_query_yaml(
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
        assert list(query.apply([sources])) == [
            {"name": "b", "rank": 1},
            {"name": "c", "rank": 2},
            {"name": "a", "rank": 3},
        ]

    def test_derive_sort_after_select(self) -> None:
        """``sort.derive`` runs on the catalog produced by
        ``select.derive`` — ``by:`` resolves against an alias that
        only exists in the projected catalog."""
        query = Query(
            from_=From(name="tasks"),
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

    def test_apply_join_after_flatten(self) -> None:
        """``join.on.left`` resolves a name introduced by ``flatten`` —
        running join before flatten would leave the join-key attribute
        living inside an array."""
        sources = {
            "cats": [
                {"id": "A", "info": [{"name": "Apple"}]},
                {"id": "B", "info": [{"name": "Beta"}]},
            ],
            "tasks": [
                {"id": "A1", "owner": "Apple"},
                {"id": "B1", "owner": "Beta"},
            ],
        }
        query = _parse_query_yaml(
            """
                from: cats
                flatten: { of: info, as: info }
                join:
                  to: tasks
                  on: { left: info.name, right: owner }
                  as: tasks
                select:
                  - item: id
                  - item: tasks
                """
        )
        assert list(query.apply([sources])) == [
            {"id": "A", "tasks": [{"id": "A1", "owner": "Apple"}]},
            {"id": "B", "tasks": [{"id": "B1", "owner": "Beta"}]},
        ]

    def test_apply_pre_join_where_filters_right_before_merge(self) -> None:
        """``join.where:`` drops right rows before the merge — left rows
        whose only matches got filtered end up with an empty list,
        not removed.  Contrast with ``test_apply_where_after_join``
        where a top-level ``where:`` would drop the left row too."""
        sources = {
            "cats": [{"id": "A"}, {"id": "B"}],
            "tasks": [
                {"id": "A1", "cat": "A", "open": True},
                {"id": "A2", "cat": "A", "open": False},
                {"id": "B1", "cat": "B", "open": False},
            ],
        }
        query = _parse_query_yaml(
            """
                from: cats
                join:
                  to: tasks
                  on: { left: id, right: cat }
                  where:
                    open: true
                  as: tasks
                select:
                  - item: id
                  - item: tasks
                """
        )
        assert list(query.apply([sources])) == [
            {"id": "A", "tasks": [{"id": "A1", "cat": "A", "open": True}]},
            {"id": "B", "tasks": []},
        ]

    def test_apply_where_after_join(self) -> None:
        """``where`` references ``tasks`` — a key that only appears
        after join attaches it.  If ``where`` ran before join, every
        row would be filtered out as missing the key."""
        sources = {
            "cats": [{"id": "A"}, {"id": "B"}],
            "tasks": [
                {"id": "A1", "cat": "A"},
                {"id": "B1", "cat": "B"},
            ],
        }
        query = _parse_query_yaml(
            """
                from: cats
                join:
                  to: tasks
                  on: { left: id, right: cat }
                  as: tasks
                where:
                  tasks: { exists: true }
                select:
                  - item: id
                  - item: tasks
                """
        )
        assert list(query.apply([sources])) == [
            {"id": "A", "tasks": [{"id": "A1", "cat": "A"}]},
            {"id": "B", "tasks": [{"id": "B1", "cat": "B"}]},
        ]

    def test_derive_join_emits_nested_entity(self) -> None:
        """``Query.derive`` end-to-end with a join: the resulting view
        catalog has the joined entity as a nested object[] child."""
        query = _parse_query_yaml(
            """
                from: cats
                join:
                  to: tasks
                  on: { left: id, right: cat }
                  as: tasks
                select:
                  - item: id
                  - item: tasks
                """
        )
        root = dc.build_tree(_catalog(_CATS_TASKS_CATALOG_YAML))
        assert dc.flatten_tree(query.derive(root), "cat_tasks") == _catalog(
            """
            - id: cat_tasks
              item_type:
                id: cat_tasks.item
                origin_item_type: cat_tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    child_entity: cat_tasks.tasks
                    child_item_type: cat_tasks.item.tasks.item
            - id: cat_tasks.tasks
              item_type:
                id: cat_tasks.item.tasks.item
                origin_item_type: tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: title, type: string, required: true }
                  - { id: cat, type: string, required: true }
              parent_entity: cat_tasks
            """
        )

    def test_apply_multi_join_chained_via_flatten_as(self) -> None:
        """A later ``join.on.left`` resolves a scalar introduced by an
        earlier ``join[].flatten.as`` — the multi-join chaining pattern
        from queries-spec ("多 join"). Running the joins in a single
        ``Sequence[Join]`` keeps this composition local; if the second
        join ran in isolation it would not see ``customer.address_id``
        as a scalar attribute on the row."""
        sources = {
            "orders": [
                {"id": "O1", "customer_id": "C1"},
                {"id": "O2", "customer_id": "C2"},
            ],
            "customers": [
                {"id": "C1", "address_id": "A1"},
                {"id": "C2", "address_id": "A2"},
            ],
            "addresses": [
                {"id": "A1", "city": "Tokyo"},
                {"id": "A2", "city": "Osaka"},
            ],
        }
        query = _parse_query_yaml(
            """
                from: orders
                join:
                  - to: customers
                    on: { left: customer_id, right: id }
                    as: customer
                    flatten: true
                  - to: addresses
                    on: { left: customer.address_id, right: id }
                    as: address
                    flatten: true
                select:
                  - item: id
                  - item: address
                """
        )
        assert list(query.apply([sources])) == [
            {"id": "O1", "address": {"id": "A1", "city": "Tokyo"}},
            {"id": "O2", "address": {"id": "A2", "city": "Osaka"}},
        ]

    def test_derive_multi_join_chained_via_flatten_as(self) -> None:
        """Catalog-side counterpart of ``test_apply_multi_join_*``:
        the second join's ``on.left`` lookup must succeed against the
        post-flatten catalog produced by the first join. If the chain
        were broken (e.g. first join left ``customer`` as an array),
        ``customer.address_id`` would be an array crossing and
        ``Merge.derive`` would raise."""
        catalog = dc.build_tree(
            _catalog(
                """
                - id: orders
                  item_type:
                    id: orders.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: customer_id, type: string, required: true }
                - id: customers
                  item_type:
                    id: customers.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: address_id, type: string, required: true }
                - id: addresses
                  item_type:
                    id: addresses.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: city, type: string, required: true }
                """
            )
        )
        query = _parse_query_yaml(
            """
                from: orders
                join:
                  - to: customers
                    on: { left: customer_id, right: id }
                    as: customer
                    flatten: true
                  - to: addresses
                    on: { left: customer.address_id, right: id }
                    as: address
                    flatten: true
                select:
                  - item: id
                  - item: address
                """
        )
        attrs = {e.name: e for e, _ in query.derive(catalog).children}
        assert attrs["id"].type == "string"
        assert attrs["address"].type == "object"

    def test_apply_flatten_chain_in_order(self) -> None:
        """Later entries in a ``Sequence[Flatten]`` take earlier
        entries' unwind output as input — the second unwind multiplies
        over the first."""
        sources = {"members": [{"id": 1, "hobbies": ["h1"], "pets": ["p1", "p2"]}]}
        query = _parse_query_yaml(
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
        assert list(query.apply([sources])) == [
            {"id": 1, "hobby": "h1", "pet": "p1"},
            {"id": 1, "hobby": "h1", "pet": "p2"},
        ]


class TestQueryOptionalClauses:
    """``flatten``/``join``/``where``/``grouped``/``sort`` are all optional;
    ``Query.apply`` / ``Query.derive`` skip ``None``/empty clauses."""

    def test_apply_without_grouped(self) -> None:
        sources = {"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}
        query = Query(
            from_=From(name="items"),
            select=Select(items=[SelectItem(item="name", as_="name")]),
        )
        assert list(query.apply([sources])) == [{"name": "a"}, {"name": "b"}]

    def test_derive_without_grouped(self) -> None:
        query = Query(
            from_=From(name="tasks"),
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


class TestQueryDeriveErrorTranslation:
    """``Query.derive`` translates ``dc.UnknownChildError`` raised by
    any clause into ``QueryDeriveError`` while preserving ``offender``,
    so the outer layer can build a user-facing diagnostic."""

    def test_unknown_attribute_surfaces_as_query_derive_error(self) -> None:
        # ``sort.by`` points at an attribute not projected by ``select``.
        # ``Sort.derive`` raises ``dc.UnknownChildError``, which
        # ``Query.derive`` translates into ``QueryDeriveError``.
        query = Query(
            from_=From(name="tasks"),
            select=Select(items=[SelectItem(item="title", as_="title")]),
            sort=Sort(by="phase"),
        )
        root = dc.build_tree(_catalog(_TOP_LEVEL_TASKS_CATALOG_YAML))
        with pytest.raises(QueryDeriveError, match="phase") as exc_info:
            query.derive(root)
        assert exc_info.value.offender == "phase"


class TestQueryFromDict:
    def test_full_query(self) -> None:
        """All clauses present: ``Query.from_dict`` assembles every
        clause into the final Query dataclass.  Non-default
        ``direction`` / ``missing`` on ``sort`` cover the enum lookups
        that Query.from_dict does inline (Sort has no own from_dict)."""
        raw = {
            "from": "items",
            "flatten": [{"of": "tags", "as": "tag", "preserve_empty": False}],
            "join": [
                {
                    "to": "owners",
                    "on": {"left": "owner_id", "right": "id"},
                    "as": "owner",
                }
            ],
            "where": {"open": True},
            "grouped": {"by": "category", "as": "members"},
            "select": [{"item": "category", "as": "category"}],
            "sort": {"by": "category", "direction": "desc", "missing": "first"},
        }
        assert Query.from_dict(raw) == Query(
            from_=From(name="items"),
            flatten=(Flatten(of="tags", as_="tag", preserve_empty=False),),
            join=(
                Join(
                    right=Query(from_=From(name="owners")),
                    merge=Merge(on_left="owner_id", on_right="id", right_as="owner"),
                ),
            ),
            where=Where(
                predicate=FieldPredicate(
                    key_path="open", operator=Operator.EQ, target=True
                ),
            ),
            grouped=Grouped(by="category", as_="members"),
            select=Select(items=[SelectItem(item="category", as_="category")]),
            sort=Sort(by="category", direction=Direction.DESC, missing=Missing.FIRST),
        )

    def test_minimal_query_uses_passthrough_for_absent_clauses(self) -> None:
        """All optional clauses absent: each field defaults to
        ``PassThrough`` (or an empty tuple for the list-typed
        clauses)."""
        query = Query.from_dict({"from": "items"})
        assert query.from_ == From(name="items")
        assert tuple(query.flatten) == ()
        assert tuple(query.join) == ()
        assert query.where == PassThrough()
        assert query.grouped == PassThrough()
        assert query.select == PassThrough()
        assert query.sort == PassThrough()

    def test_parses_join_list_form_multiple_items_preserves_order(self) -> None:
        """List entries become a ``Sequence[Join]`` in declared order;
        ``Query.apply`` / ``Query.derive`` rely on this ordering for
        multi-join chaining (later ``on.left`` can refer to attributes
        introduced by earlier ``flatten.as``)."""
        raw = {
            "from": "orders",
            "join": [
                {
                    "to": "customers",
                    "on": {"left": "customer_id", "right": "id"},
                    "as": "customer",
                    "flatten": {
                        "of": "customer",
                        "as": "customer",
                        "preserve_empty": False,
                    },
                },
                {
                    "to": "addresses",
                    "on": {"left": "customer.address_id", "right": "id"},
                    "as": "address",
                },
            ],
            "select": [{"item": "id", "as": "id"}],
        }
        joins = list(Query.from_dict(raw).join)
        assert [j.merge.right_as for j in joins] == ["customer", "address"]
        assert [j.merge.on_left for j in joins] == [
            "customer_id",
            "customer.address_id",
        ]


def _catalog_name(field_name: str) -> str:
    """Translate a dataclass field name into its catalog edge name.

    DSL dataclasses use PEP 8 trailing underscores to dodge Python
    keyword conflicts (``from_`` / ``as_``); the catalog edge names use
    the bare YAML keys (``from`` / ``as``). Stripping the trailing
    underscore is the full translation.
    """
    return field_name.removesuffix("_")


def _ref_query(from_: str, *join_tos: str) -> Query:
    """A minimal query reading ``from_`` and joining each of ``join_tos``.

    Clause payloads beyond the source names are irrelevant to
    ``source_names`` / ``evaluation_order``, so the join condition is a
    placeholder.
    """
    return Query(
        from_=From(name=from_),
        join=tuple(
            Join(
                right=Query(from_=From(name=to)),
                merge=Merge(on_left="id", on_right="id", right_as=to),
            )
            for to in join_tos
        ),
    )


class TestSourceNames:
    """Query.source_names: the names a query reads, in clause order."""

    def test_from_only(self) -> None:
        assert Query(from_=From(name="tasks")).source_names() == ("tasks",)

    def test_includes_each_join_target(self) -> None:
        query = _parse_query_yaml(
            """
            from: tasks
            join:
              - to: categories
                on: { left: category_id, right: id }
              - to: phases
                on: { left: phase_id, right: id }
            """
        )
        assert query.source_names() == ("tasks", "categories", "phases")

    def test_collects_join_right_sources_recursively(self) -> None:
        """``from_dict`` only ever builds a join's right side as a bare
        ``from:`` wrapper today, but source_names must not depend on
        that shallowness — a richer right side contributes everything
        it reads."""
        query = Query(
            from_=From(name="tasks"),
            join=(
                Join(
                    right=_ref_query("categories", "phases"),
                    merge=Merge(on_left="id", on_right="id", right_as="c"),
                ),
            ),
        )
        assert query.source_names() == ("tasks", "categories", "phases")


class TestEvaluationOrder:
    """evaluation_order: the wrapper over ``graphlib.TopologicalSorter``.

    The sort itself is graphlib's; these cover only what this function
    adds — building query→query dependencies from ``source_names`` and
    turning a cycle into a positioned ``QueryDeriveError``.
    """

    def test_from_reference_orders_referenced_first(self) -> None:
        queries = {"a": _ref_query("b"), "b": _ref_query("items")}
        assert evaluation_order(queries) == ["b", "a"]

    def test_join_reference_orders_referenced_first(self) -> None:
        # The dependency rides on ``join.to``, not just ``from``.
        queries = {"a": _ref_query("items", "b"), "b": _ref_query("items")}
        assert evaluation_order(queries) == ["b", "a"]

    def test_data_entity_sources_impose_no_ordering(self) -> None:
        # ``items`` is not a key of ``queries``, so it is a data entity
        # and creates no dependency edge.
        queries = {"a": _ref_query("items", "items")}
        assert evaluation_order(queries) == ["a"]

    def test_cycle_reported_in_reference_direction(self) -> None:
        # a reads b, b reads c, c reads a — the message must read forward
        # along the references, not along graphlib's predecessor order.
        with pytest.raises(QueryDeriveError) as exc_info:
            evaluation_order(
                {"a": _ref_query("b"), "b": _ref_query("c"), "c": _ref_query("a")}
            )
        assert "a → b → c → a" in str(exc_info.value)

    def test_offender_is_the_reference_that_closes_the_cycle(self) -> None:
        # ``a`` closes the cycle onto itself via a join to ``b`` (its
        # ``from`` names the unrelated data entity ``items``).  The
        # offender must be that ``b`` reference — anchoring the diagnostic
        # at the ``join.to`` position, not at ``a``'s name or its ``from``.
        queries = {"a": _ref_query("items", "b"), "b": _ref_query("a")}
        with pytest.raises(QueryDeriveError) as exc_info:
            evaluation_order(queries)
        assert exc_info.value.offender == "b"


class TestCatalogDriftSuppression:
    """Assert ``Query.catalog`` stays in sync with the Query dataclass.

    The catalog edge names use bare YAML keys, while the dataclasses use
    PEP 8 trailing-underscore names where the YAML key collides with a
    Python keyword. :func:`_catalog_name` bridges the two.

    ``id`` on a query record is synthesized by ``Query.from_dict`` from the
    dict-pattern key and has no Query dataclass field — the test
    includes it explicitly in the expected set.
    """

    def test_query_edges_match_dataclass_fields(self) -> None:
        assert {edge.name for edge, _ in Query.catalog.children} == {"id"} | {
            _catalog_name(f.name) for f in dataclasses.fields(Query)
        }
