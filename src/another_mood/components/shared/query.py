"""Query DSL — object model and evaluation.

Each DSL element (From / Grouped / Select / SelectItem / Where /
Query) is a ``QueryNode``: it pairs a record transform with a catalog
transform derived from the same DSL fragment.  The two transforms
compose along the same pipeline so that the resulting schema can be
inspected without evaluating data.  See
dev-docs/internal/components/composer.md for the duality rationale.

The ``where`` clause's per-record predicate AST lives in
:mod:`record_predicate`; :class:`Where` here is just the pipeline
wrapper.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, ClassVar, Protocol, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.json_data_model import pluck, split_path
from another_mood.components.shared.record_predicate import (
    RecordPredicate,
    UnknownKeyPathError,
    parse_record_predicate,
)

type Record = Mapping[str, object]


class QueryDeriveError(Exception):
    """Raised when a query references an identifier missing from the catalog.

    The outer layer inspects ``offender`` (the user-input identifier value)
    to build a user-facing diagnostic — when ``offender`` carries source
    provenance (a ``UserStr`` from ``parse_yaml``), the diagnostic can
    point back at the originating YAML position.
    """

    def __init__(self, message: str, *, offender: str) -> None:
        super().__init__(message)
        self.offender = offender


@runtime_checkable
class QueryNode(Protocol):
    """A query DSL element with a paired record transform and schema transform.

    The two transforms compose along the same pipeline so that the resulting
    schema can be inspected without evaluating data.
    """

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        """Transform input rows into output rows."""
        ...

    def derive(self, catalog: dc.Node) -> dc.Node:
        """Transform the input catalog node into the output catalog node.

        Mirrors ``apply`` on the schema side: takes the catalog tree the
        previous stage produced and returns the catalog tree the next stage
        will consume, without touching record data.
        """
        ...


@dataclass(frozen=True)
class SelectItem:
    """A single field projection (rename ``item`` to ``as_``)."""

    item: str
    as_: str

    def apply(self, record: Record) -> tuple[str, object]:
        return (self.as_, pluck(record, self.item))

    def derive(self, catalog: dc.Node) -> tuple[dc.Edge, dc.Node]:
        if not catalog.has_child(self.item):
            raise QueryDeriveError(
                f"unknown attribute '{self.item}'", offender=self.item
            )
        edge, child = catalog.child_entry(self.item)
        return (replace(edge, name=self.as_), child)


@dataclass(frozen=True)
class Select(QueryNode):
    """Project named fields from each input row, optionally renaming them."""

    items: Sequence[SelectItem]

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return [
            {name: value for s in self.items for name, value in [s.apply(record)]}
            for record in records
        ]

    def derive(self, catalog: dc.Node) -> dc.Node:
        return dc.Node(children=[item.derive(catalog) for item in self.items])


@dataclass(frozen=True)
class From(QueryNode):
    """Walks a dot-path through nested object[] arrays to a leaf data source."""

    path: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        remaining = self.path
        while remaining:
            records, remaining = flatten_children(records, remaining)
        return records

    def derive(self, catalog: dc.Node) -> dc.Node:
        try:
            return catalog.walk_path(self.path)
        except KeyError as exc:
            raise QueryDeriveError(
                f"unknown entity '{self.path}'", offender=self.path
            ) from exc


def flatten_children(
    parents: Sequence[Mapping[str, object]], key_path: str
) -> tuple[Sequence[Record], str]:
    """Consume one longest-match step of ``key_path`` from each parent
    and deep-flatten its value into a list of objects.

    Returns ``(records, remaining_key_path)``.  Walks any depth of
    nested arrays; a single object is taken as-is.
    """
    if not parents:
        return ([], "")

    # Determine the directly-applicable key sequence from the first parent;
    # parents at the same level share a shape per the catalog.
    keys, remaining = split_path(parents[0], key_path)
    if remaining and not keys:
        # First parent couldn't consume even one step — treat as miss.
        raise KeyError(key_path)

    result: list[Record] = []
    for parent in parents:
        result.extend(_flatten_nd_pure_array(pluck(parent, keys)))
    return (result, remaining)


def _flatten_nd_pure_array(v: object) -> list[Record]:
    """Flatten a Mapping or (possibly nested) list of Mappings."""
    if isinstance(v, Mapping):
        return [cast(Record, v)]
    elif isinstance(v, list):
        return [
            r for item in cast(list[object], v) for r in _flatten_nd_pure_array(item)
        ]
    else:
        raise TypeError(f"expected Mapping or list of Mappings, got {type(v).__name__}")


@dataclass(frozen=True)
class Grouped(QueryNode):
    """Group input rows by ``by`` and package each group under ``as_``.

    Grouped rows are preserved verbatim (including their own ``by`` field).
    """

    by: str
    as_: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        groups: dict[object, list[Record]] = {}
        for record in records:
            groups.setdefault(pluck(record, self.by), []).append(record)
        return [{self.by: key, self.as_: items} for key, items in groups.items()]

    def derive(self, catalog: dc.Node) -> dc.Node:
        if not catalog.has_child(self.by):
            raise QueryDeriveError(f"unknown attribute '{self.by}'", offender=self.by)
        return dc.Node(
            children=[
                catalog.child_entry(self.by),
                (
                    dc.Edge(name=self.as_, type="object[]", required=True),
                    catalog,
                ),
            ],
        )


@dataclass(frozen=True)
class Where(QueryNode):
    """Pipeline wrapper around a :class:`RecordPredicate` tree."""

    predicate: RecordPredicate

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return [r for r in records if self.predicate.matches(r)]

    def derive(self, catalog: dc.Node) -> dc.Node:
        # Schema transform is identity (where filters records only);
        # the call still validates key_path references and translates
        # the predicate-side error so :mod:`record_predicate` need not
        # know about :class:`QueryDeriveError`.
        try:
            self.predicate.validate_by_catalog(catalog)
        except UnknownKeyPathError as exc:
            raise QueryDeriveError(str(exc), offender=exc.key_path) from exc
        return catalog


class Direction(Enum):
    """Sort direction.  Enum value = YAML key."""

    ASC = "asc"
    DESC = "desc"


class Missing(Enum):
    """Missing-key placement in a sort.  Enum value = YAML key."""

    FIRST = "first"
    LAST = "last"


@dataclass(frozen=True)
class Sort(QueryNode):
    """Order output records by a single attribute."""

    by: str
    direction: Direction = Direction.ASC
    missing: Missing = Missing.LAST

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        keyed: list[tuple[Any, Record]] = []
        absent: list[Record] = []
        for record in records:
            try:
                keyed.append((pluck(record, self.by), record))
            except KeyError:
                absent.append(record)
        ordered = [
            r
            for _, r in sorted(
                keyed, key=lambda kv: kv[0], reverse=self.direction is Direction.DESC
            )
        ]
        return absent + ordered if self.missing is Missing.FIRST else ordered + absent

    def derive(self, catalog: dc.Node) -> dc.Node:
        # Schema transform is identity (sort reorders only); call still
        # validates that ``by`` resolves in the catalog.
        try:
            catalog.walk_path(self.by)
        except KeyError as exc:
            raise QueryDeriveError(
                f"unknown attribute '{self.by}'", offender=self.by
            ) from exc
        return catalog


@dataclass(frozen=True)
class Query(QueryNode):
    """Pipeline of clauses applied in the order
    ``from → where? → grouped? → select → sort?``."""

    select: Select
    from_: From
    grouped: Grouped | None
    where: Where | None = None
    sort: Sort | None = None

    #: Catalog self-description of a persisted query record.
    catalog: ClassVar[dc.Node] = dc.Node(
        children=[
            (dc.Edge(name="id", type="string", required=True), dc.Node()),
            (dc.Edge(name="from", type="string", required=True), dc.Node()),
            (dc.Edge(name="where", type="object", required=False), dc.Node()),
            (dc.Edge(name="grouped", type="object", required=False), dc.Node()),
            (dc.Edge(name="select", type="object", required=False), dc.Node()),
            (dc.Edge(name="sort", type="object", required=False), dc.Node()),
        ],
    )

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        records = self.from_.apply(records)
        if self.where is not None:
            records = self.where.apply(records)
        if self.grouped:
            records = self.grouped.apply(records)
        records = self.select.apply(records)
        if self.sort is not None:
            records = self.sort.apply(records)
        return records

    def derive(self, catalog: dc.Node) -> dc.Node:
        node = self.from_.derive(catalog)
        if self.where is not None:
            node = self.where.derive(node)
        if self.grouped:
            node = self.grouped.derive(node)
        node = self.select.derive(node)
        if self.sort is not None:
            node = self.sort.derive(node)
        return node


def parse_query(raw: Mapping[str, object]) -> Query:
    """Parse a YAML-loaded query record into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_raw = cast(str, raw["from"])
    from_ = From(path=from_raw)

    where: Where | None = None
    if "where" in raw:
        where = Where(
            predicate=parse_record_predicate(cast(Mapping[str, object], raw["where"]))
        )

    grouped: Grouped | None = None
    if "grouped" in raw:
        grouped_raw = cast(Mapping[str, str], raw["grouped"])
        grouped = Grouped(
            by=grouped_raw["by"],
            as_=grouped_raw.get("as", from_raw.rsplit(".", 1)[-1]),
        )

    select_raw = cast(Sequence[Mapping[str, str]], raw.get("select", []))
    select = Select(
        items=[
            SelectItem(item=entry["item"], as_=entry.get("as", entry["item"]))
            for entry in select_raw
        ]
    )

    sort: Sort | None = None
    if "sort" in raw:
        sort_raw = cast(Mapping[str, str], raw["sort"])
        sort = Sort(
            by=sort_raw["by"],
            direction=Direction(sort_raw.get("direction", "asc")),
            missing=Missing(sort_raw.get("missing", "last")),
        )

    return Query(select=select, from_=from_, grouped=grouped, where=where, sort=sort)
