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
from typing import ClassVar, Protocol, cast, runtime_checkable

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
    """A single field projection (rename ``item`` to ``as_``)."""

    item: str
    as_: str

    #: Node-form self-description of a persisted select-item record.
    #: A Node whose children mirror the SelectItem record's YAML keys
    #: (``item`` and ``as``).  Composed into ``Query.catalog`` as the
    #: child node of the ``select`` edge.
    catalog: ClassVar[dc.Node] = dc.Node(
        children=[
            (dc.Edge(name="item", type="string", required=True), dc.Node()),
            (dc.Edge(name="as", type="string", required=False), dc.Node()),
        ],
    )

    def apply(self, record: Record) -> tuple[str, object]:
        return (self.as_, record[self.item])

    def derive(self, catalog: dc.Node) -> tuple[dc.Edge, dc.Node]:
        if not catalog.has_child(self.item):
            raise QueryDeriveError(
                f"unknown attribute '{self.item}'", offender=self.item
            )
        edge, child = catalog.child_entry(self.item)
        return (replace(edge, name=self.as_), child)


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
        try:
            return catalog.walk_path(self.path)
        except KeyError as exc:
            raise QueryDeriveError(
                f"unknown entity '{self.path}'", offender=self.path
            ) from exc


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
    """Group input rows by ``by`` and package each group under ``as_``.

    Grouped rows are preserved verbatim (including their own ``by`` field).
    """

    by: str
    as_: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        groups: dict[object, list[Record]] = {}
        for record in records:
            groups.setdefault(record[self.by], []).append(record)
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
class Query:
    """Pipeline of clauses applied in the order ``from → grouped? → select``."""

    select: Select
    from_: From
    grouped: Grouped | None

    #: Node-form self-description of a persisted query record.
    #: Mirrors how a query appears in YAML after normalization: ``id``
    #: synthesized from the dict-pattern key, ``from`` and ``select``
    #: from the DSL keys, and ``grouped`` singleton-flattened into
    #: ``grouped.by`` / ``grouped.as``.  The ``select`` edge carries
    #: ``SelectItem.catalog`` as the child-entity link.
    #:
    #: The caller (inspect_schema) assigns the catalog id
    #: ``__definition.queries`` via ``to_flat`` and sets ``builtin=True``
    #: before persisting.
    catalog: ClassVar[dc.Node] = dc.Node(
        children=[
            (dc.Edge(name="id", type="string", required=True), dc.Node()),
            (dc.Edge(name="from", type="string", required=True), dc.Node()),
            (dc.Edge(name="grouped", type="object", required=False), dc.Node()),
            (dc.Edge(name="grouped.by", type="string", required=True), dc.Node()),
            (
                dc.Edge(name="grouped.as", type="string", required=False),
                dc.Node(),
            ),
            (
                dc.Edge(name="select", type="object[]", required=False),
                SelectItem.catalog,
            ),
        ],
    )

    def apply(self, parents: Sequence[Record]) -> Sequence[Record]:
        records = self.from_.apply(parents)
        if self.grouped:
            records = self.grouped.apply(records)
        return self.select.apply(records)

    def derive(self, catalog: dc.Node) -> dc.Node:
        node = self.from_.derive(catalog)
        if self.grouped:
            node = self.grouped.derive(node)
        return self.select.derive(node)


def parse_query(raw: Mapping[str, object]) -> Query:
    """Parse a YAML-loaded query record into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_raw = cast(str, raw["from"])
    from_ = From(path=from_raw)

    grouped: Grouped | None = None
    if "grouped" in raw:
        grouped_raw = cast(Mapping[str, str], raw["grouped"])
        grouped = Grouped(
            by=grouped_raw["by"],
            as_=grouped_raw.get("as", from_.segments[-1]),
        )

    select_raw = cast(Sequence[Mapping[str, str]], raw.get("select", []))
    select = Select(
        items=[
            SelectItem(item=entry["item"], as_=entry.get("as", entry["item"]))
            for entry in select_raw
        ]
    )

    return Query(select=select, from_=from_, grouped=grouped)
