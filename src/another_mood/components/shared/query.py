"""Query DSL — object model and evaluation.

Each DSL element (From / Grouped / Select / SelectItem / Query) is a
``QueryNode``: it pairs a record transform with a catalog transform
derived from the same DSL fragment.  The two transforms compose along
the same pipeline so that the resulting schema can be inspected without
evaluating data.  See dev-docs/internal/components/composer.md for the
duality rationale.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc

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
    """A single field projection (rename ``item`` to ``as_name``)."""

    item: str
    as_name: str

    def apply(self, record: Record) -> tuple[str, object]:
        return (self.as_name, record[self.item])

    def derive(self, catalog: dc.Node) -> tuple[dc.Edge, dc.Node]:
        if not catalog.has_child(self.item):
            raise QueryDeriveError(
                f"unknown attribute '{self.item}'", offender=self.item
            )
        edge, child = catalog.child_entry(self.item)
        return (replace(edge, name=self.as_name), child)


@dataclass(frozen=True)
class Select:
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
class From:
    """Walks a dot-path through nested object[] arrays to a leaf data source."""

    path: str

    @property
    def segments(self) -> Sequence[str]:
        return self.path.split(".")

    def apply(self, parents: Sequence[Record]) -> Sequence[Record]:
        records = parents
        for key in self.segments:
            records = flatten_children(records, key)
        return records

    def derive(self, catalog: dc.Node) -> dc.Node:
        node = catalog
        for segment in self.segments:
            if not node.has_child(segment):
                raise QueryDeriveError(
                    f"unknown entity '{self.path}'", offender=self.path
                )
            node = node.child(segment)
        return node


def flatten_children(
    parents: Iterable[Mapping[str, object]], child_key: str
) -> Sequence[Record]:
    """Deep-flatten each parent's child_key into a sequence of objects.

    Walks through any depth of nested arrays; a single object is taken
    as-is. Non-object leaves are not expected (entity-addressed paths
    only reach objects or arrays of objects, possibly nested).
    """
    result: list[Record] = []

    def _walk(v: object) -> None:
        if isinstance(v, Mapping):
            result.append(cast(Record, v))
            return
        for item in cast(Sequence[object], v):
            _walk(item)

    for parent in parents:
        _walk(parent[child_key])
    return result


@dataclass(frozen=True)
class Grouped:
    """Group input rows by ``by`` and package each group under ``as_name``.

    Grouped rows are preserved verbatim (including their own ``by`` field).
    """

    by: str
    as_name: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        groups: dict[object, list[Record]] = {}
        for record in records:
            groups.setdefault(record[self.by], []).append(record)
        return [{self.by: key, self.as_name: items} for key, items in groups.items()]

    def derive(self, catalog: dc.Node) -> dc.Node:
        if not catalog.has_child(self.by):
            raise QueryDeriveError(f"unknown attribute '{self.by}'", offender=self.by)
        return dc.Node(
            children=[
                catalog.child_entry(self.by),
                (
                    dc.Edge(name=self.as_name, type="object[]", required=True),
                    catalog,
                ),
            ],
        )


@dataclass(frozen=True)
class Query:
    """Pipeline of clauses applied in the order ``from → grouped? → select``."""

    select: Select
    from_clause: From
    grouped: Grouped | None

    def apply(self, parents: Sequence[Record]) -> Sequence[Record]:
        records = self.from_clause.apply(parents)
        if self.grouped:
            records = self.grouped.apply(records)
        return self.select.apply(records)

    def derive(self, catalog: dc.Node) -> dc.Node:
        node = self.from_clause.derive(catalog)
        if self.grouped:
            node = self.grouped.derive(node)
        return self.select.derive(node)


def parse_query(raw: Mapping[str, object]) -> Query:
    """Parse a YAML-loaded query record into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_raw = cast(str, raw["from"])
    from_clause = From(path=from_raw)

    grouped: Grouped | None = None
    if "grouped" in raw:
        grouped_raw = cast(Mapping[str, str], raw["grouped"])
        grouped = Grouped(
            by=grouped_raw["by"],
            as_name=grouped_raw.get("as", from_clause.segments[-1]),
        )

    select_raw = cast(Sequence[Mapping[str, str]], raw.get("select", []))
    select = Select(
        items=[
            SelectItem(item=entry["item"], as_name=entry.get("as", entry["item"]))
            for entry in select_raw
        ]
    )

    return Query(select=select, from_clause=from_clause, grouped=grouped)
