"""Record-predicate sub-DSL backing the ``where`` clause.

Four sum-type variants form a :class:`RecordPredicate`:
:class:`FieldPredicate` (atomic) and :class:`And` / :class:`Or` /
:class:`Not` (combinators).  Pipeline integration (``apply`` /
``derive``) lives on the ``Where`` wrapper in :mod:`query`.

See ``dev-docs/design/composer/queries-spec.md`` for the spec.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeGuard, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.json_data_model import pluck

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


class UnknownKeyPathError(Exception):
    """A ``key_path`` does not resolve in the catalog.

    Defined here rather than imported from :mod:`query` so this module
    has no reverse dependency.  :meth:`query.Where.derive` translates
    it into ``QueryDeriveError`` with source-location provenance.
    """

    def __init__(self, key_path: str) -> None:
        super().__init__(f"unknown attribute '{key_path}'")
        self.key_path = key_path


@runtime_checkable
class RecordPredicate(Protocol):
    def matches(self, record: Record) -> bool: ...

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        """Raise :class:`UnknownKeyPathError` for any unresolved
        ``key_path`` — catches typos that would otherwise degrade
        :meth:`matches` to a silent always-false filter."""
        ...


@dataclass(frozen=True)
class FieldPredicate(RecordPredicate):
    """One field, one predicate.  ``key_path`` may be a dotted path.

    ``parse_record_predicate`` unfolds the YAML sugar
    ``{ age: { gt: 10, lt: 20 } }`` into an :class:`And` of singletons,
    so the AST stays one-predicate-per-leaf.
    """

    key_path: str
    operator: Operator
    target: object

    def matches(self, record: Record) -> bool:
        try:
            value: object = pluck(record, self.key_path)
        except KeyError:
            value = MISSING
        return self.operator.evaluate(value, self.target)

    def validate_by_catalog(self, catalog: dc.Node) -> None:
        try:
            catalog.walk_path(self.key_path)
        except KeyError as exc:
            raise UnknownKeyPathError(self.key_path) from exc


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
    """Parse one whereClause.  Multiple top-level keys → :class:`And`
    (the spec's implicit-AND rule); a single key returns its sole
    child unwrapped."""
    clauses: list[RecordPredicate] = []
    for key, value in raw.items():
        if key == "and":
            clauses.append(
                And(
                    clauses=[
                        parse_record_predicate(cast(Mapping[str, object], child))
                        for child in cast(Sequence[object], value)
                    ]
                )
            )
        elif key == "or":
            clauses.append(
                Or(
                    clauses=[
                        parse_record_predicate(cast(Mapping[str, object], child))
                        for child in cast(Sequence[object], value)
                    ]
                )
            )
        elif key == "not":
            clauses.append(
                Not(
                    clause=parse_record_predicate(cast(Mapping[str, object], value)),
                )
            )
        else:
            clauses.append(_parse_field_predicate(key, value))
    if len(clauses) == 1:
        return clauses[0]
    return And(clauses=clauses)


def _parse_field_predicate(key_path: str, value: object) -> RecordPredicate:
    if isinstance(value, Mapping):
        items = [
            (Operator(name), target)
            for name, target in cast(Mapping[str, object], value).items()
        ]
    else:
        items = [(Operator.EQ, value)]
    if len(items) == 1:
        op, target = items[0]
        return FieldPredicate(key_path=key_path, operator=op, target=target)
    return And(
        clauses=[
            FieldPredicate(key_path=key_path, operator=op, target=target)
            for op, target in items
        ],
    )
