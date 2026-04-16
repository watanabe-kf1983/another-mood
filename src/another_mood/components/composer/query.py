"""Query DSL — object model and evaluation."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

type Record = Mapping[str, object]


@dataclass(frozen=True)
class SelectItem:
    """A single field projection in a select clause."""

    item: str
    as_name: str

    def apply(self, record: Record) -> tuple[str, object]:
        """Return (output_name, value) for this projection."""
        return (self.as_name, record[self.item])


@dataclass(frozen=True)
class Select:
    """A select clause — projects fields from each record."""

    items: Sequence[SelectItem]

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        """Project fields from each record."""
        return [
            {name: value for s in self.items for name, value in [s.apply(record)]}
            for record in records
        ]


@dataclass(frozen=True)
class From:
    """A from clause — flatten a dot-path from parent records.

    The initial parent is the root sources mapping (wrapped in a
    single-element list by the caller). Each path segment extracts and
    concatenates the named child array.
    """

    path: Sequence[str]

    def apply(self, parents: Sequence[Record]) -> Sequence[Record]:
        """Flatten the path over the given parents."""
        records = parents
        for key in self.path:
            records = flatten_children(records, key)
        return records


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
    """A group-by clause."""

    by: str
    as_name: str

    def apply(self, records: Sequence[Record]) -> Sequence[Record]:
        """Group records by key field."""
        groups: dict[object, list[Record]] = {}
        for record in records:
            groups.setdefault(record[self.by], []).append(record)
        return [{self.by: key, self.as_name: items} for key, items in groups.items()]


@dataclass(frozen=True)
class Query:
    """A parsed query definition."""

    select: Select
    from_clause: From
    grouped: Grouped | None

    def apply(self, parents: Sequence[Record]) -> Sequence[Record]:
        """Evaluate this query: from → grouped → select."""
        records = self.from_clause.apply(parents)
        if self.grouped:
            records = self.grouped.apply(records)
        return self.select.apply(records)
