"""Tests for the where-clause record-predicate AST."""

from collections.abc import Mapping, Sequence

import pytest
from ruamel.yaml import YAML

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.record_predicate import (
    MISSING,
    And,
    FieldPredicate,
    Not,
    Operator,
    Or,
    RecordPredicate,
    parse_record_predicate,
)

type Record = Mapping[str, object]


def _fp(key_path: str, **preds: object) -> FieldPredicate | And:
    """Build a per-field predicate.  One kwarg → :class:`FieldPredicate`;
    multiple kwargs → :class:`And` of singletons (mirrors the parser)."""
    items = [(Operator(name), target) for name, target in preds.items()]
    if len(items) == 1:
        op, target = items[0]
        return FieldPredicate(key_path=key_path, operator=op, target=target)
    return And(
        clauses=[
            FieldPredicate(key_path=key_path, operator=op, target=target)
            for op, target in items
        ],
    )


class TestOperatorEvaluate:
    """Per-operator evaluation: :meth:`Operator.evaluate`."""

    @pytest.mark.parametrize(
        ("value", "target", "expected"),
        [
            ("open", "open", True),
            ("open", "closed", False),
            (1, 1, True),
            (1, "1", False),  # Python equality across types
            (MISSING, "open", False),  # sentinel identity differs
        ],
    )
    def test_eq(self, value: object, target: object, expected: bool) -> None:
        assert Operator.EQ.evaluate(value, target) is expected

    @pytest.mark.parametrize(
        ("op", "value", "target", "expected"),
        [
            (Operator.GT, 11, 10, True),
            (Operator.GT, 10, 10, False),
            (Operator.GTE, 10, 10, True),
            (Operator.GTE, 9, 10, False),
            (Operator.LT, 9, 10, True),
            (Operator.LT, 10, 10, False),
            (Operator.LTE, 10, 10, True),
            (Operator.LTE, 11, 10, False),
            (Operator.GT, 1.5, 1, True),  # int / float interop
            # non-numeric value filters out (no TypeError)
            (Operator.GT, "11", 10, False),
            (Operator.GT, True, 0, False),  # bool excluded
            (Operator.GT, MISSING, 10, False),
        ],
    )
    def test_ordering(
        self, op: Operator, value: object, target: object, expected: bool
    ) -> None:
        assert op.evaluate(value, target) is expected

    @pytest.mark.parametrize(
        ("op", "value", "target", "expected"),
        [
            (Operator.STARTSWITH, "cat.a", "cat.", True),
            (Operator.STARTSWITH, "dog", "cat.", False),
            (Operator.ENDSWITH, "a.md", ".md", True),
            (Operator.ENDSWITH, "a.md", ".yaml", False),
            (Operator.CONTAINS, "phase 10", "phase", True),
            (Operator.CONTAINS, "design", "phase", False),
            # non-string value filters out
            (Operator.STARTSWITH, 123, "x", False),
            (Operator.STARTSWITH, True, "x", False),
            (Operator.CONTAINS, MISSING, "x", False),
        ],
    )
    def test_string_pattern(
        self, op: Operator, value: object, target: object, expected: bool
    ) -> None:
        assert op.evaluate(value, target) is expected

    @pytest.mark.parametrize(
        ("value", "target", "expected"),
        [
            ("any value", True, True),
            (MISSING, True, False),
            ("any value", False, False),
            (MISSING, False, True),
            # falsy non-missing values count as present
            ("", True, True),
            (0, True, True),
        ],
    )
    def test_exists(self, value: object, target: object, expected: bool) -> None:
        assert Operator.EXISTS.evaluate(value, target) is expected


class TestOperatorTargetTypeAssertion:
    """``_to_numeric`` / ``_to_string`` raise on schema mismatch.

    Per the spec ``target`` types are constrained by JSON Schema; these
    raise rather than silently coerce so an upstream schema bug
    surfaces loudly.
    """

    def test_ordering_with_non_numeric_target_raises(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            Operator.GT.evaluate(11, "10")

    def test_string_pattern_with_non_string_target_raises(self) -> None:
        with pytest.raises(TypeError, match="string"):
            Operator.STARTSWITH.evaluate("cat", 42)


class TestFieldPredicateMatches:
    """Wiring: pluck ``key_path``, substitute :data:`MISSING` on
    ``KeyError``, dispatch to :meth:`Operator.evaluate`."""

    def test_resolves_dotted_key_path(self) -> None:
        assert _fp("hobby.active", eq=True).matches(
            {"hobby": {"active": True}},
        )

    def test_missing_key_observable_via_exists(self) -> None:
        assert _fp("absent", exists=False).matches({})
        assert not _fp("absent", exists=True).matches({})

    def test_dispatches_to_operator(self) -> None:
        # Any one non-trivial operator exercises the dispatch path.
        assert _fp("n", gt=5).matches({"n": 10})
        assert not _fp("n", gt=5).matches({"n": 1})


_T = _fp("ok", eq=True)
_F = _fp("ok", eq=False)


class TestCombinators:
    @pytest.mark.parametrize(
        ("clauses", "expected"),
        [
            ([_T], True),
            ([_T, _T], True),
            ([_T, _F], False),
            ([_F, _T], False),
            ([], True),  # vacuous AND
        ],
    )
    def test_and(self, clauses: Sequence[RecordPredicate], expected: bool) -> None:
        assert And(clauses=clauses).matches({"ok": True}) is expected

    @pytest.mark.parametrize(
        ("clauses", "expected"),
        [
            ([_T], True),
            ([_F, _T], True),
            ([_F, _F], False),
            ([], False),  # vacuous OR
        ],
    )
    def test_or(self, clauses: Sequence[RecordPredicate], expected: bool) -> None:
        assert Or(clauses=clauses).matches({"ok": True}) is expected

    @pytest.mark.parametrize(
        ("clause", "expected"),
        [(_T, False), (_F, True)],
    )
    def test_not(self, clause: RecordPredicate, expected: bool) -> None:
        assert Not(clause=clause).matches({"ok": True}) is expected

    def test_not_on_missing_key_keeps_record(self) -> None:
        """``not (eq: x)`` on a missing key flips ``False`` → ``True``,
        confirming the inner ``matches`` returns ``False`` for absent
        fields and the outer ``Not`` inverts it."""
        assert Not(clause=_fp("id", eq="x")).matches({}) is True


def _catalog(yaml_text: str) -> list[dc.Entity]:
    loaded: list[dict[str, object]] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return [dc.Entity.from_dict(e) for e in loaded]


_TASKS_CATALOG = """
- id: tasks
  item_type:
    id: tasks.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: phase, type: integer, required: false }
"""


class TestValidateByCatalog:
    """``validate_by_catalog`` walks ``key_path`` references and raises
    :class:`dc.UnknownChildError` on misses; combinators recurse."""

    @pytest.fixture
    def catalog(self) -> dc.Node:
        return dc.build_tree(_catalog(_TASKS_CATALOG)).child("tasks")

    def test_field_predicate_resolves(self, catalog: dc.Node) -> None:
        FieldPredicate(
            key_path="phase", operator=Operator.GT, target=5
        ).validate_by_catalog(catalog)

    def test_field_predicate_raises_on_unknown(self, catalog: dc.Node) -> None:
        with pytest.raises(dc.UnknownChildError, match="nonexistent"):
            FieldPredicate(
                key_path="nonexistent", operator=Operator.EQ, target=1
            ).validate_by_catalog(catalog)

    @pytest.mark.parametrize(
        "combinator",
        [
            And(
                clauses=[
                    FieldPredicate(key_path="phase", operator=Operator.GT, target=5),
                    FieldPredicate(key_path="bad", operator=Operator.EQ, target=1),
                ],
            ),
            Or(
                clauses=[
                    FieldPredicate(key_path="phase", operator=Operator.GT, target=5),
                    FieldPredicate(key_path="bad", operator=Operator.EQ, target=1),
                ],
            ),
            Not(
                clause=FieldPredicate(key_path="bad", operator=Operator.EQ, target=1),
            ),
        ],
        ids=["and", "or", "not"],
    )
    def test_combinator_propagates(
        self, combinator: RecordPredicate, catalog: dc.Node
    ) -> None:
        with pytest.raises(dc.UnknownChildError, match="bad"):
            combinator.validate_by_catalog(catalog)

    def test_rejects_key_path_crossing_array(self) -> None:
        catalog = dc.build_tree(
            _catalog(
                """
                - id: members
                  item_type:
                    id: members.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - id: tasks
                        type: object[]
                        required: true
                        child_entity: members.tasks
                        child_item_type: members.item.tasks.item
                - id: members.tasks
                  item_type:
                    id: members.item.tasks.item
                    attributes:
                      - { id: title, type: string, required: true }
                  parent_entity: members
                """
            )
        ).child("members")
        with pytest.raises(dc.UnknownChildError, match="tasks.title"):
            FieldPredicate(
                key_path="tasks.title", operator=Operator.EQ, target="x"
            ).validate_by_catalog(catalog)


class TestParseRecordPredicate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param(
                {"name": "alice"},
                FieldPredicate(key_path="name", operator=Operator.EQ, target="alice"),
                id="scalar_sugars_to_eq",
            ),
            pytest.param(
                {"age": {"gt": 10}},
                FieldPredicate(key_path="age", operator=Operator.GT, target=10),
                id="single_predicate_unwraps",
            ),
            pytest.param(
                {"a": 1, "b": 2},
                And(
                    clauses=[
                        FieldPredicate(key_path="a", operator=Operator.EQ, target=1),
                        FieldPredicate(key_path="b", operator=Operator.EQ, target=2),
                    ],
                ),
                id="multi_top_level_keys_wrap_in_and",
            ),
            pytest.param(
                {"age": {"gt": 10, "lt": 20}},
                And(
                    clauses=[
                        FieldPredicate(key_path="age", operator=Operator.GT, target=10),
                        FieldPredicate(key_path="age", operator=Operator.LT, target=20),
                    ],
                ),
                id="multi_predicate_bundle_unfolds_into_and",
            ),
            pytest.param(
                {"and": [{"a": 1}, {"b": 2}]},
                And(
                    clauses=[
                        FieldPredicate(key_path="a", operator=Operator.EQ, target=1),
                        FieldPredicate(key_path="b", operator=Operator.EQ, target=2),
                    ],
                ),
                id="explicit_and",
            ),
            pytest.param(
                {"or": [{"x": 1}, {"x": 2}]},
                Or(
                    clauses=[
                        FieldPredicate(key_path="x", operator=Operator.EQ, target=1),
                        FieldPredicate(key_path="x", operator=Operator.EQ, target=2),
                    ],
                ),
                id="explicit_or",
            ),
            pytest.param(
                {"not": {"id": {"startswith": "__"}}},
                Not(
                    clause=FieldPredicate(
                        key_path="id",
                        operator=Operator.STARTSWITH,
                        target="__",
                    ),
                ),
                id="explicit_not_unwraps_single_inner",
            ),
        ],
    )
    def test_parse(self, raw: Mapping[str, object], expected: RecordPredicate) -> None:
        assert parse_record_predicate(raw) == expected
