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
from functools import reduce
from itertools import chain
from typing import Any, ClassVar, Protocol, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.json_data_model import pluck
from another_mood.components.shared.record_predicate import (
    RecordPredicate,
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

    def derive(self, catalog: dc.Node) -> Sequence[tuple[dc.Edge, dc.Node]]:
        # Pull dotted siblings too so derive mirrors apply's ``pluck``,
        # which returns the whole singleton object.
        catalog.require_child(self.item)
        prefix = self.item + "."
        return [
            (replace(edge, name=self.as_ + edge.name.removeprefix(self.item)), node)
            for edge, node in catalog.children
            if edge.name == self.item or edge.name.startswith(prefix)
        ]


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
        return dc.Node(
            children=list(
                chain.from_iterable(item.derive(catalog) for item in self.items)
            )
        )


@dataclass(frozen=True)
class From(QueryNode):
    """Read all rows of one entity by direct name lookup."""

    name: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        (wrapper,) = records
        value = pluck(wrapper, self.name)
        assert isinstance(value, list), (
            f"from '{self.name}' must resolve to a list; got {type(value).__name__}"
        )
        return cast(Sequence[Record], value)

    def derive(self, catalog: dc.Node) -> dc.Node:
        if not catalog.has_child(self.name):
            raise QueryDeriveError(f"unknown entity '{self.name}'", offender=self.name)
        return catalog.child(self.name)


@dataclass(frozen=True)
class Flatten(QueryNode):
    """Unwind one array attribute: each element becomes a separate row
    carrying the parent's other fields plus the element under ``as_``."""

    of: str
    as_: str
    preserve_empty: bool = False

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return list(chain.from_iterable(self._unwind(parent) for parent in records))

    def derive(self, catalog: dc.Node) -> dc.Node:
        edge, child = catalog.child_entry(self.of)
        if not edge.type.endswith("[]"):
            raise QueryDeriveError(
                f"flatten target '{self.of}' is not an array attribute "
                f"(type '{edge.type}')",
                offender=self.of,
            )
        if self.as_ != self.of and catalog.has_child(self.as_):
            raise QueryDeriveError(
                f"flatten alias '{self.as_}' collides with an existing attribute",
                offender=self.as_,
            )
        wrapper = replace(
            edge,
            name=self.as_,
            type=edge.type[:-2],
            required=not self.preserve_empty,
        )
        # Inline as ``<as_>.X`` siblings — catalog convention for
        # singleton sub-objects (see data_catalog._build_entity_node).
        inlined = [
            (replace(sub_edge, name=f"{self.as_}.{sub_edge.name}"), sub_node)
            for sub_edge, sub_node in child.children
        ]
        return dc.Node(
            metadata=catalog.metadata,
            children=list(
                chain.from_iterable(
                    [(wrapper, dc.Node()), *inlined] if e.name == self.of else [(e, c)]
                    for e, c in catalog.children
                )
            ),
        )

    def _unwind(self, parent: Record) -> Sequence[Record]:
        other = {k: v for k, v in parent.items() if k != self.of}
        try:
            raw = pluck(parent, self.of)
        except KeyError:
            raw = []
        assert isinstance(raw, list), (
            f"flatten target '{self.of}' must be an array; got {type(raw).__name__}"
        )
        children = cast(list[object], raw)
        if self.preserve_empty and not children:
            return [other]
        return [{**other, self.as_: child} for child in children]


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
        # call still validates predicate key_paths against the catalog.
        self.predicate.validate_by_catalog(catalog)
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
        catalog.require_child(self.by)
        return catalog


@dataclass(frozen=True)
class Query(QueryNode):
    """Pipeline of clauses applied in the order
    ``from → flatten? → where? → grouped? → select → sort?``."""

    select: Select
    from_: From
    grouped: Grouped | None
    flatten: Sequence[Flatten] = ()
    where: Where | None = None
    sort: Sort | None = None

    #: Catalog self-description of a persisted query record.
    catalog: ClassVar[dc.Node] = dc.Node(
        children=[
            (dc.Edge(name="id", type="string", required=True), dc.Node()),
            (dc.Edge(name="from", type="string", required=True), dc.Node()),
            (dc.Edge(name="flatten", type="object", required=False), dc.Node()),
            (dc.Edge(name="where", type="object", required=False), dc.Node()),
            (dc.Edge(name="grouped", type="object", required=False), dc.Node()),
            (dc.Edge(name="select", type="object", required=False), dc.Node()),
            (dc.Edge(name="sort", type="object", required=False), dc.Node()),
        ],
    )

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return reduce(lambda r, qn: qn.apply(r), self._pipeline(), records)

    def derive(self, catalog: dc.Node) -> dc.Node:
        try:
            return reduce(lambda c, qn: qn.derive(c), self._pipeline(), catalog)
        except dc.UnknownChildError as exc:
            raise QueryDeriveError(
                f"unknown attribute '{exc.name}'", offender=exc.name
            ) from exc

    def _pipeline(self) -> Sequence[QueryNode]:
        clauses = (
            self.from_,
            *self.flatten,
            self.where,
            self.grouped,
            self.select,
            self.sort,
        )
        return [c for c in clauses if c is not None]


def parse_query(raw: Mapping[str, object]) -> Query:
    """Parse a YAML-loaded query record into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_raw = cast(str, raw["from"])
    from_ = From(name=from_raw)

    flatten: Sequence[Flatten] = (
        parse_flatten(raw["flatten"]) if "flatten" in raw else ()
    )

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

    return Query(
        select=select,
        from_=from_,
        grouped=grouped,
        flatten=flatten,
        where=where,
        sort=sort,
    )


def parse_flatten(raw: object) -> Sequence[Flatten]:
    """Parse the three accepted shapes of the ``flatten:`` clause.

    * bare string  → one shorthand entry
    * mapping      → one object-form entry
    * sequence     → list-form, each entry either shorthand or object form
    """
    if isinstance(raw, str):
        return [_flatten_from_shorthand(raw)]
    if isinstance(raw, Mapping):
        return [_flatten_from_mapping(cast(Mapping[str, object], raw))]
    if isinstance(raw, Sequence):
        return [
            _flatten_from_shorthand(entry)
            if isinstance(entry, str)
            else _flatten_from_mapping(cast(Mapping[str, object], entry))
            for entry in cast(Sequence[object], raw)
        ]
    raise TypeError(
        f"flatten clause must be a string, mapping, or list; got {type(raw).__name__}"
    )


def _flatten_from_shorthand(name: str) -> Flatten:
    return Flatten(of=name, as_=name)


def _flatten_from_mapping(raw: Mapping[str, object]) -> Flatten:
    of = cast(str, raw["of"])
    return Flatten(
        of=of,
        as_=cast(str, raw.get("as", of)),
        preserve_empty=cast(bool, raw.get("preserve_empty", False)),
    )
