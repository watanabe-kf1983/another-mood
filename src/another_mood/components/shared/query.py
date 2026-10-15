"""Query DSL — object model and evaluation.

Each DSL element (From / Flatten / Where / Grouped / SelectItem / Select /
Sort / Query) is a ``QueryNode``: it pairs a record transform with a catalog
transform derived from the same DSL fragment.  The two transforms
compose along the same pipeline so that the resulting schema can be
inspected without evaluating data.

The ``where`` clause's per-record predicate AST lives in
:mod:`record_predicate`; :class:`Where` here is just the pipeline
wrapper.
"""

from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from functools import reduce
from graphlib import CycleError, TopologicalSorter
from itertools import chain, combinations
from typing import Any, ClassVar, Protocol, cast, runtime_checkable

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.catalog_write import (
    Placement,
    names,
    overlaps,
    place,
    remove,
    require,
    swap,
)
from another_mood.components.shared.json_data_model import KeyPath, drop, pluck, put
from another_mood.components.shared.record_predicate import (
    MISSING,
    RecordPredicate,
    parse_record_predicate,
)

type Record = Mapping[str, object]


class QueryDeriveError(Exception):
    """Raised when a query's source reference cannot be turned into a
    derivation — the referenced identifier is missing from the catalog,
    or the references between queries form a cycle.

    The outer layer inspects ``offender`` (the user-input identifier value)
    to build a user-facing diagnostic — when ``offender`` carries source
    provenance (a ``UserStr`` from ``parse_mapping``), the diagnostic can
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
class From(QueryNode):
    """Read all rows of one entity, named by its path from the root."""

    path: KeyPath

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        (wrapper,) = records
        try:
            value = pluck(wrapper, self.path)
        except KeyError:
            # A source that passed derive() is catalog-declared, but the
            # merged data model only carries keys that some content file
            # contributed to — an entity whose records were all deleted
            # has no key at all.  Absent means zero rows.
            return []
        assert isinstance(value, list), (
            f"from '{'.'.join(self.path)}' must resolve to a list; "
            f"got {type(value).__name__}"
        )
        return cast(Sequence[Record], value)

    def derive(self, catalog: dc.Node) -> dc.Node:
        name = ".".join(self.path)
        try:
            edge, node = catalog.descend(self.path)
        except dc.UnknownChildError:
            # The first segment carries the path's source position.
            raise QueryDeriveError(
                f"unknown source '{name}'", offender=self.path[0]
            ) from None
        if not dc.is_entity(edge, node):
            # A singleton or a scalar resolves but holds no rows.
            raise QueryDeriveError(
                f"source '{name}' is not an entity (type '{edge.type}')",
                offender=self.path[0],
            )
        return node


@dataclass(frozen=True)
class Flatten(QueryNode):
    """Unwind one array attribute: each element becomes a separate row
    carrying the parent's other fields plus the element under ``as_``."""

    of: KeyPath
    as_: KeyPath
    preserve_empty: bool = False

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return list(chain.from_iterable(self._unwind(parent) for parent in records))

    def derive(self, catalog: dc.Node) -> dc.Node:
        edges, child = catalog.reach(self.of)
        edge = edges[-1]
        if not edge.is_collection:
            raise QueryDeriveError(
                f"flatten target '{'.'.join(self.of)}' is not an array attribute "
                f"(type '{edge.type}')",
                offender=self.of[0],
            )
        source: KeyPath = (*self.of, "[]") if self.preserve_empty else ()
        kept = catalog if self.preserve_empty else require(catalog, self.of[:-1])
        rest = remove(kept, self.of)
        taken = next((name for name in names(rest) if overlaps(self.as_, name)), None)
        if taken is not None:
            raise QueryDeriveError(
                f"flatten alias '{'.'.join(self.as_)}' collides with the attribute "
                f"'{'.'.join(taken)}'",
                offender=self.as_[0],
            )
        element = (replace(edge, type=edge.type[:-2]), child)
        if self.as_[:-1] == self.of[:-1]:
            landed = replace(
                element[0], name=self.as_[-1], required=not self.preserve_empty
            )
            out = swap(kept, self.of, (landed, child))
        else:
            out = place(rest, [Placement(branch=element, path=self.as_, source=source)])
        # A row is no longer an instance of the item type it came from.
        return replace(out, origin_item_type=None)

    def _unwind(self, parent: Record) -> Sequence[Record]:
        other = drop(parent, self.of)
        try:
            raw = pluck(parent, self.of)
        except KeyError:
            raw = []
        assert isinstance(raw, list), (
            f"flatten target '{self.of[-1]}' must be an array; got {type(raw).__name__}"
        )
        children = cast(list[object], raw)
        if self.preserve_empty and not children:
            return [other]
        return [put(other, self.as_, child) for child in children]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Flatten":
        return cls(
            of=tuple(cast(Sequence[str], raw["of"])),
            as_=tuple(cast(Sequence[str], raw["as"])),
            preserve_empty=cast(bool, raw["preserve_empty"]),
        )


@dataclass(frozen=True)
class Merge:
    """Equi-join with default cardinality: attach matched right rows
    as a list at ``right_as`` on each left row.  Both ``on_*``
    paths follow the asymmetry rule: reaching into nested objects is
    allowed, crossing an array is not.
    """

    on_left: KeyPath
    on_right: KeyPath
    right_as: KeyPath

    def apply(
        self,
        left: Sequence[Record],
        right: Sequence[Record],
    ) -> Sequence[Record]:
        index: dict[object, list[Record]] = {}
        for r in right:
            try:
                key = pluck(r, self.on_right)
            except KeyError:
                continue
            index.setdefault(key, []).append(r)

        def _matched(row: Record) -> list[Record]:
            try:
                return index.get(pluck(row, self.on_left), [])
            except KeyError:
                return []

        return [put(row, self.right_as, _matched(row)) for row in left]

    def derive(self, left: dc.Node, right: dc.Node) -> dc.Node:
        left.require_path(self.on_left)
        right.require_path(self.on_right)
        taken = next(
            (name for name in names(left) if overlaps(self.right_as, name)), None
        )
        if taken is not None:
            raise QueryDeriveError(
                f"join alias '{'.'.join(self.right_as)}' collides with the attribute "
                f"'{'.'.join(taken)}'",
                offender=self.right_as[0],
            )
        # Every left row gets its list (empty on no match), so the
        # branch is on every row.
        attached = (
            dc.Edge(name=self.right_as[-1], type="object[]", required=True),
            right,
        )
        out = place(left, [Placement(branch=attached, path=self.right_as, source=())])
        # A row is no longer an instance of the item type it came from.
        return replace(out, origin_item_type=None)


@dataclass(frozen=True)
class Join:
    """Attach a right relation, with an optional inline flatten.
    ``apply`` / ``derive`` run ``right`` → ``merge`` → optional
    ``flatten`` in sequence; ``right`` reads the outer Query's sources.

    Deliberately not a ``QueryNode``: it is the only two-input clause, and
    ``Query.apply`` / ``Query.derive`` spell out the pipeline order around
    it rather than widening the one-in one-out protocol for a single case.
    """

    right: "Query"
    merge: Merge
    flatten: Flatten | None = None

    def apply(
        self, left: Sequence[Record], sources: Sequence[Record]
    ) -> Sequence[Record]:
        out = self.merge.apply(left, self.right.apply(sources))
        return self.flatten.apply(out) if self.flatten is not None else out

    def derive(self, left: dc.Node, root_catalog: dc.Node) -> dc.Node:
        out = self.merge.derive(left, self.right.derive(root_catalog))
        return self.flatten.derive(out) if self.flatten is not None else out

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Join":
        to = tuple(cast(Sequence[str], raw["to"]))
        on_raw = cast(Mapping[str, Sequence[str]], raw["on"])
        where: Where | PassThrough = PassThrough()
        if "where" in raw:
            where = Where.from_dict(cast(Mapping[str, object], raw["where"]))
        flatten = (
            Flatten.from_dict(cast(Mapping[str, object], raw["flatten"]))
            if "flatten" in raw
            else None
        )
        return cls(
            right=Query(from_=From(path=to), where=where),
            merge=Merge(
                on_left=tuple(on_raw["left"]),
                on_right=tuple(on_raw["right"]),
                right_as=tuple(cast(Sequence[str], raw["as"])),
            ),
            flatten=flatten,
        )


@dataclass(frozen=True)
class Where(QueryNode):
    """Pipeline wrapper around a :class:`RecordPredicate` tree."""

    predicate: RecordPredicate

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return [r for r in records if self.predicate.matches(r)]

    def derive(self, catalog: dc.Node) -> dc.Node:
        self.predicate.validate_by_catalog(catalog)
        return catalog

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Where":
        return cls(predicate=parse_record_predicate(raw))


@dataclass(frozen=True)
class Grouped(QueryNode):
    """Group input rows by ``by`` and package each group under ``as_``.

    Grouped rows are preserved verbatim (including their own ``by`` field).
    Rows lacking ``by`` form one group of their own, whose row omits ``by``.
    """

    by: KeyPath
    as_: KeyPath

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        groups: dict[object, list[Record]] = {}
        for record in records:
            groups.setdefault(self._key_of(record), []).append(record)
        return [self._group_row(key, items) for key, items in groups.items()]

    def derive(self, catalog: dc.Node) -> dc.Node:
        if overlaps(self.by, self.as_):
            raise QueryDeriveError(
                f"grouped alias '{'.'.join(self.as_)}' collides with the grouping "
                f"key '{'.'.join(self.by)}'",
                offender=self.as_[0],
            )
        key = SelectItem(item=self.by, as_=self.by).derive(catalog)
        # Every group has its rows, so the list is on every group row.
        members = Placement(
            branch=(
                dc.Edge(name=self.as_[-1], type="object[]", required=True),
                catalog,
            ),
            path=self.as_,
            source=(),
        )
        # The group row is built from nothing, like a projection.
        return place(dc.Node(), [key, members])

    def _key_of(self, record: Record) -> object:
        try:
            return pluck(record, self.by)
        except KeyError:
            return MISSING

    def _group_row(self, key: object, items: Sequence[Record]) -> Record:
        empty: Record = {}
        row = empty if key is MISSING else put(empty, self.by, key)
        return put(row, self.as_, items)

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Grouped":
        return cls(
            by=tuple(cast(Sequence[str], raw["by"])),
            as_=tuple(cast(Sequence[str], raw["as"])),
        )


@dataclass(frozen=True)
class SelectItem:
    """A single field projection: read ``item``, write it at ``as_``.

    Both are paths.
    """

    item: KeyPath
    as_: KeyPath

    def apply(self, record: Record, out: Record) -> Record:
        """Return ``out`` with the source value written at :attr:`as_`,
        or ``out`` untouched when the source field is absent — no null and
        no empty object to hang the path from, so rows vary in key set.
        """
        try:
            value = pluck(record, self.item)
        except KeyError:
            return out
        return put(out, self.as_, value)

    def derive(self, catalog: dc.Node) -> Placement:
        """The branch read at :attr:`item`, bound for :attr:`as_`."""
        # The whole subtree comes along, mirroring apply's ``pluck``.
        edges, node = catalog.reach(self.item)
        # The deepest optional edge on the way: a row holds it exactly when
        # it holds the value, since every edge below is required and every
        # edge above is there whenever it is.
        optional_depths = [
            depth for depth, edge in enumerate(edges, 1) if not edge.required
        ]
        return Placement(
            branch=(edges[-1], node),
            path=self.as_,
            source=tuple(e.name for e in edges[: max(optional_depths, default=0)]),
        )


@dataclass(frozen=True)
class Select(QueryNode):
    """Project named fields from each input row, optionally renaming them."""

    items: Sequence[SelectItem]

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return [self._project(record) for record in records]

    def derive(self, catalog: dc.Node) -> dc.Node:
        # Every two aliases must be clear of each other.  The item
        # reported is the later of the pair -- the write that would land
        # on or inside the earlier one.  Its first segment carries the
        # alias's source position.
        for earlier, later in combinations([item.as_ for item in self.items], 2):
            if overlaps(earlier, later):
                raise QueryDeriveError(
                    f"select alias '{'.'.join(later)}' collides with an earlier "
                    f"item '{'.'.join(earlier)}'",
                    offender=later[0],
                )
        # The row is built from nothing, so nothing the input held under
        # the same name carries over.
        return place(dc.Node(), [item.derive(catalog) for item in self.items])

    def _project(self, record: Record) -> Record:
        empty: Record = {}
        return reduce(lambda out, item: item.apply(record, out), self.items, empty)

    @classmethod
    def from_dict(cls, raw: Sequence[Mapping[str, object]]) -> "Select":
        return cls(
            items=[
                SelectItem(
                    item=tuple(cast(Sequence[str], entry["item"])),
                    as_=tuple(cast(Sequence[str], entry["as"])),
                )
                for entry in raw
            ]
        )


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

    by: KeyPath
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
        catalog.require_path(self.by)
        return catalog


@dataclass(frozen=True)
class PassThrough(QueryNode):
    """Identity stage: returns its input unchanged. Used as the default
    value of optional clauses on :class:`Query` so the pipeline body
    stays a uniform sequence of calls — no per-clause None guards."""

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        return records

    def derive(self, catalog: dc.Node) -> dc.Node:
        return catalog


@dataclass(frozen=True)
class Query(QueryNode):
    """Pipeline of clauses applied in the order
    ``from → flatten* → join* → where? → grouped? → select → sort?``."""

    from_: From
    flatten: Sequence[Flatten] = ()
    join: Sequence[Join] = ()
    where: Where | PassThrough = PassThrough()
    grouped: Grouped | PassThrough = PassThrough()
    select: Select | PassThrough = PassThrough()
    sort: Sort | PassThrough = PassThrough()

    #: Catalog self-description of a persisted query record.
    catalog: ClassVar[dc.Node] = dc.Node(
        children=[
            (dc.Edge(name="id", type="string", required=True), dc.Node()),
            (dc.Edge(name="from", type="string[]", required=True), dc.Node()),
            (dc.Edge(name="flatten", type="object", required=False), dc.Node()),
            (dc.Edge(name="join", type="object", required=False), dc.Node()),
            (dc.Edge(name="where", type="object", required=False), dc.Node()),
            (dc.Edge(name="grouped", type="object", required=False), dc.Node()),
            (dc.Edge(name="select", type="object", required=False), dc.Node()),
            (dc.Edge(name="sort", type="object", required=False), dc.Node()),
        ],
    )

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        out = self.from_.apply(records)
        for f in self.flatten:
            out = f.apply(out)
        for j in self.join:
            out = j.apply(out, records)
        out = self.where.apply(out)
        out = self.grouped.apply(out)
        out = self.select.apply(out)
        out = self.sort.apply(out)
        return out

    def derive(self, catalog: dc.Node) -> dc.Node:
        try:
            out = self.from_.derive(catalog)
            for f in self.flatten:
                out = f.derive(out)
            for j in self.join:
                out = j.derive(out, catalog)
            out = self.where.derive(out)
            out = self.grouped.derive(out)
            out = self.select.derive(out)
            out = self.sort.derive(out)
            return out
        except dc.UnknownChildError as exc:
            # The first segment carries the path's source position.
            raise QueryDeriveError(
                f"unknown attribute '{'.'.join(exc.path)}'", offender=exc.path[0]
            ) from exc

    def source_paths(self) -> Sequence[KeyPath]:
        return (
            self.from_.path,
            *chain.from_iterable(join.right.source_paths() for join in self.join),
        )

    def query_references(self, query_names: Container[str]) -> Sequence[str]:
        """The names in ``query_names`` this query reads from.

        A query is named by one segment (query names hold no dot), so a
        longer source path never refers to one.
        """
        return [
            path[0]
            for path in self.source_paths()
            if len(path) == 1 and path[0] in query_names
        ]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Query":
        """Build a Query from a canonical query record.

        This is the Any-to-typed boundary: canonical query data comes
        in (sugar expanded, optional defaults filled by upstream
        normalization), validated Query objects come out.
        """
        from_ = From(path=tuple(cast(Sequence[str], raw["from"])))

        flatten: Sequence[Flatten] = tuple(
            Flatten.from_dict(entry)
            for entry in cast(Sequence[Mapping[str, object]], raw.get("flatten", ()))
        )

        join: Sequence[Join] = tuple(
            Join.from_dict(entry)
            for entry in cast(Sequence[Mapping[str, object]], raw.get("join", ()))
        )

        where: Where | PassThrough = PassThrough()
        if "where" in raw:
            where = Where.from_dict(cast(Mapping[str, object], raw["where"]))

        grouped: Grouped | PassThrough = PassThrough()
        if "grouped" in raw:
            grouped = Grouped.from_dict(cast(Mapping[str, object], raw["grouped"]))

        select_raw = cast(Sequence[Mapping[str, object]], raw.get("select", []))
        select: Select | PassThrough = (
            Select.from_dict(select_raw) if select_raw else PassThrough()
        )

        sort: Sort | PassThrough = PassThrough()
        if "sort" in raw:
            sort_raw = cast(Mapping[str, object], raw["sort"])
            sort = Sort(
                by=tuple(cast(Sequence[str], sort_raw["by"])),
                direction=Direction(cast(str, sort_raw["direction"])),
                missing=Missing(cast(str, sort_raw["missing"])),
            )

        return cls(
            from_=from_,
            flatten=flatten,
            join=join,
            where=where,
            grouped=grouped,
            select=select,
            sort=sort,
        )


def evaluation_order(queries: Mapping[str, Query]) -> Sequence[str]:
    """Order query names so each is preceded by the queries it reads.

    A query's dependencies are its references to another query in
    ``queries``; other sources impose no ordering.
    Raises :class:`QueryDeriveError` if these references form a cycle.
    """
    deps = {name: q.query_references(queries) for name, q in queries.items()}
    try:
        return list(TopologicalSorter(deps).static_order())
    except CycleError as exc:
        # graphlib reports the cycle in predecessor order (dependency →
        # dependent); reverse it to reference order (reader → target),
        # matching how a query names the source it reads.
        cycle = list(reversed(exc.args[1]))
        # ``cycle[0]`` reads ``cycle[1]``; use that reference's own value
        # as the offender — taken from the query, not from ``cycle``, so
        # the anchor doesn't depend on which string instance graphlib
        # surfaces in the cycle.
        offender = next(
            s for s in queries[cycle[0]].query_references(queries) if s == cycle[1]
        )
        raise QueryDeriveError(
            "query reference cycle: " + " → ".join(cycle), offender=offender
        ) from exc
