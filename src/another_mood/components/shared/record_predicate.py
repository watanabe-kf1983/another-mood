"""Record-predicate sub-DSL backing the ``where`` clause.

Four sum-type variants form a :class:`RecordPredicate`:
:class:`FieldPredicate` (atomic) and :class:`And` / :class:`Or` /
:class:`Not` (combinators).  Pipeline integration (``apply`` /
``derive``) lives on the ``Where`` wrapper in :mod:`query`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeGuard, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.json_data_model import KeyPath, pluck

type Record = Mapping[str, object]


#: Sentinel passed to :meth:`Operator.evaluate` for an absent field.
#: ``object()`` produces a fresh identity so ``value is MISSING`` is
#: unambiguous against any user-supplied value.
MISSING: object = object()


class Operator(Enum):
    """The closed set of atomic predicates.  Enum value = YAML key."""

    EQ = "eq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    STARTSWITH = "startswith"
    ENDSWITH = "endswith"
    CONTAINS = "contains"
    EXISTS = "exists"

    def evaluate(self, value: object, target: object) -> bool:
        match self:
            case Operator.EXISTS:
                return (value is not MISSING) is bool(target)
            case Operator.EQ:
                return value == target
            case Operator.GT:
                return _is_numeric(value) and value > _to_numeric(target)
            case Operator.GTE:
                return _is_numeric(value) and value >= _to_numeric(target)
            case Operator.LT:
                return _is_numeric(value) and value < _to_numeric(target)
            case Operator.LTE:
                return _is_numeric(value) and value <= _to_numeric(target)
            case Operator.STARTSWITH:
                return isinstance(value, str) and value.startswith(_to_string(target))
            case Operator.ENDSWITH:
                return isinstance(value, str) and value.endswith(_to_string(target))
            case Operator.CONTAINS:
                return isinstance(value, str) and _to_string(target) in value


def _is_numeric(v: object) -> TypeGuard[int | float]:
    # ``bool`` is an ``int`` subclass; exclude explicitly to keep the
    # numeric and boolean domains disjoint.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _to_numeric(v: object) -> int | float:
    if not _is_numeric(v):
        raise TypeError(f"expected numeric target; got {type(v).__name__}: {v!r}")
    return v


def _to_string(v: object) -> str:
    if not isinstance(v, str):
        raise TypeError(f"expected string target; got {type(v).__name__}: {v!r}")
    return v


@runtime_checkable
class RecordPredicate(Protocol):
    def matches(self, record: Record) -> bool: ...

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        """Raise :class:`dc.UnknownChildError` for any unresolved
        ``field`` — catches typos that would otherwise degrade
        :meth:`matches` to a silent always-false filter."""
        ...


@dataclass(frozen=True)
class FieldPredicate(RecordPredicate):
    """One field, one predicate.  ``field`` may reach into nested objects."""

    field: KeyPath
    operator: Operator
    target: object

    def matches(self, record: Record) -> bool:
        try:
            value: object = pluck(record, self.field)
        except KeyError:
            value = MISSING
        return self.operator.evaluate(value, self.target)

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        catalog.require_path(self.field)


@dataclass(frozen=True)
class And(RecordPredicate):
    clauses: Sequence[RecordPredicate]

    def matches(self, record: Record) -> bool:
        return all(clause.matches(record) for clause in self.clauses)

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        for clause in self.clauses:
            clause.validate_by_catalog(catalog)


@dataclass(frozen=True)
class Or(RecordPredicate):
    clauses: Sequence[RecordPredicate]

    def matches(self, record: Record) -> bool:
        return any(clause.matches(record) for clause in self.clauses)

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        for clause in self.clauses:
            clause.validate_by_catalog(catalog)


@dataclass(frozen=True)
class Not(RecordPredicate):
    """Inner ``clause`` is a single :class:`RecordPredicate`.

    A list-typed ``not`` is forbidden at the syntax level to dodge
    the ``!(a∧b)``-vs-``[¬a, ¬b]`` ambiguity.
    """

    clause: RecordPredicate

    def matches(self, record: Record) -> bool:
        return not self.clause.matches(record)

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        self.clause.validate_by_catalog(catalog)


def parse_record_predicate(raw: Mapping[str, object]) -> RecordPredicate:
    """Build the predicate tree from one canonical ``where`` node.

    The YAML sugar (implicit AND, scalar ``eq``, operator bundles) is
    already expanded upstream, so each node maps onto one AST node.
    """
    if "and" in raw:
        return And(clauses=_parse_clauses(raw["and"]))
    elif "or" in raw:
        return Or(clauses=_parse_clauses(raw["or"]))
    elif "not" in raw:
        return Not(
            clause=parse_record_predicate(cast(Mapping[str, object], raw["not"]))
        )
    else:
        return FieldPredicate(
            field=tuple(cast(Sequence[str], raw["field"])),
            operator=Operator(cast(str, raw["operator"])),
            target=raw["target"],
        )


def _parse_clauses(raw: object) -> Sequence[RecordPredicate]:
    return [
        parse_record_predicate(cast(Mapping[str, object], child))
        for child in cast(Sequence[object], raw)
    ]
