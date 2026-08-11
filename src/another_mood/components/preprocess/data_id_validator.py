"""Record identity check — ``id`` uniqueness within a sibling collection.

The same id under two different parents names two different records
and is legitimate; only siblings compete.
"""

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from typing import cast

from another_mood.components.shared.user_source.source_loader import UserStr
from another_mood.components.shared.user_source.diagnostic import Diagnostic


def check_duplicate_ids(
    data_by_entity: Mapping[str, Sequence[Mapping[str, object]]],
) -> Sequence[Diagnostic]:
    """Diagnose records that share an ``id`` with a sibling.

    ``data_by_entity`` must already be merged across every source file.
    Every record of a colliding group is reported, so all its locations
    are named.
    """
    return [
        diagnostic
        for entity_id, records in data_by_entity.items()
        for diagnostic in _check_collection(entity_id, records)
    ]


def _check_collection(
    collection: str, values: Sequence[object]
) -> Iterator[Diagnostic]:
    records = [
        cast(Mapping[str, object], value)
        for value in values
        if isinstance(value, Mapping)
    ]
    yield from _duplicates(collection, records)
    # An array element becomes addressable through its id, so a record
    # without one — and everything under it — has no address to collide on.
    for record in records:
        if "id" in record:
            yield from _descend(f"{collection}/{record['id']}", record)


def _duplicates(
    collection: str, records: Sequence[Mapping[str, object]]
) -> Iterator[Diagnostic]:
    ids = [record["id"] for record in records if "id" in record]
    # Grouped as an address segment is, so an id written as a YAML
    # integer collides with the same id written as a string.
    counts = Counter(str(value) for value in ids)
    return (_duplicate_id(collection, value) for value in ids if counts[str(value)] > 1)


def _descend(owner: str, record: Mapping[str, object]) -> Iterator[Diagnostic]:
    # A key is always an addressable step, so an object-valued attribute
    # carries its own nested collections further down.
    for key, value in record.items():
        if isinstance(value, Mapping):
            yield from _descend(f"{owner}/{key}", cast(Mapping[str, object], value))
        elif isinstance(value, list):
            yield from _check_collection(
                f"{owner}/{key}", cast(Sequence[object], value)
            )


def _duplicate_id(collection: str, value: object) -> Diagnostic:
    location = value.location if isinstance(value, UserStr) else None
    return Diagnostic(
        file=location.file if location else None,
        line=location.line if location else None,
        column=location.column if location else None,
        message=f"duplicate id {str(value)!r} in {collection}",
        source="duplicate-id",
    )
