"""Query DSL — object model and evaluation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

type Record = Mapping[str, object]
type Sources = Mapping[str, Sequence[Record]]


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
    """A from clause — resolves a data source by name."""

    source: str

    def resolve(self, sources: Sources) -> Sequence[Record]:
        """Look up the named source and return its array."""
        data = sources.get(self.source)
        if not isinstance(data, Sequence):
            raise ValueError(f"Unknown source: '{self.source}'")
        return data


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

    def evaluate(self, sources: Sources) -> Sequence[Record]:
        """Evaluate this query against the given data sources."""
        records = self.from_clause.resolve(sources)

        if self.grouped:
            records = self.grouped.apply(records)

        return self.select.apply(records)
