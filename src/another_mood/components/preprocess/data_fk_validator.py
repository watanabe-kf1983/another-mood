"""Data-level foreign-key integrity check.

For every property declared with ``x-ref``, verify that the actual
value appears in the target attribute's value set.  Run after content
normalization so the data is already in canonical ``[{"id": ..., ...}]``
shape, regardless of whether the user wrote a dict-pattern or an
explicit array.

Position info comes from the ``UserStr`` tag carried by each scalar
string value (set up by ``source_loader.parse_mapping``), so diagnostics
point at the originating YAML line/column.  When the value is not
UserStr-tagged (e.g. data was re-loaded from disk via ``typ='safe'``,
or constructed in memory), the diagnostic still names the offending
entity / attribute / value but the file/line/column fields stay None.

Each violation is returned as a :class:`Diagnostic` with
``severity=warning`` and ``source="x-ref-data"``.
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import cast

from another_mood.components.shared.user_source.source_loader import UserStr
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared import json_data_model
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    DiagnosticSeverity,
)

#: Attribute types whose values can serve as FK targets.  Non-scalar
#: types (``object``, ``object[]``) carry dict / list values that are
#: not hashable into a target set, and could not match an x-ref value
#: anyway since the meta-schema constrains x-ref to ``type: string``.
_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})


def check_fk_data(
    catalog: Sequence[dc.Entity],
    root: Mapping[str, object],
) -> Sequence[Diagnostic]:
    """Diagnose FK values with no match in the declared target set.

    ``catalog`` carries every entity, the root entity included.  ``root``
    is the whole normalized data tree, merged across every source file.
    """
    catalog_by_id = {e.id: e for e in catalog}
    target_index = _build_target_index(catalog_by_id, root)
    return [
        _fk_violation(entity, attr, value)
        for entity, attr, value in _walk_records(
            dc.ROOT_ENTITY_ID, [root], catalog_by_id
        )
        if attr.x_ref is not None
        and value
        not in target_index.get((attr.x_ref.entity, attr.x_ref.attribute), frozenset())
    ]


def _build_target_index(
    catalog_by_id: Mapping[str, dc.Entity],
    root: Mapping[str, object],
) -> Mapping[tuple[str, str], frozenset[object]]:
    """Build ``(target_entity_id, target_attribute_id) -> value set``.

    Missing values (``None`` / absent key) are excluded so optional
    attributes do not pollute the set with an implicit null.
    """
    return {
        (entity.id, attr.id): frozenset(
            value
            for rec in records
            if (value := _attribute_value(rec, attr)) is not None
        )
        for entity, records in _root_collections(catalog_by_id, root)
        for attr in entity.item_type.attributes
        # Non-scalar attributes (singleton-flatten parents like ``body`` /
        # ``x_ref``, child-entity links) cannot be FK targets and their
        # dict/list values are unhashable.
        if attr.type in _SCALAR_TYPES
    }


def _root_collections(
    catalog_by_id: Mapping[str, dc.Entity],
    root: Mapping[str, object],
) -> Iterator[tuple[dc.Entity, Sequence[Mapping[str, object]]]]:
    """Yield each collection whose parent is the root, with its records."""
    root_entity = catalog_by_id.get(dc.ROOT_ENTITY_ID)
    if root_entity is None:
        return
    for link in root_entity.item_type.attributes:
        if link.child_entity is None:
            continue
        records = _attribute_value(root, link)
        if isinstance(records, list):
            yield (
                catalog_by_id[link.child_entity],
                cast(Sequence[Mapping[str, object]], records),
            )


def _walk_records(
    entity_id: str,
    records: Sequence[Mapping[str, object]],
    catalog_by_id: Mapping[str, dc.Entity],
) -> Iterator[tuple[dc.Entity, dc.Attribute, object]]:
    """Yield ``(entity, attr, value)`` for every populated attribute.

    Attributes that link to a nested entity (``child_entity`` set) are
    not yielded themselves; instead the walker recurses into the child
    records so the per-attribute callers see only leaf scalar values.
    Missing / null values are skipped.
    """
    entity = catalog_by_id.get(entity_id)
    if entity is None:
        return
    for record in records:
        for attr in entity.item_type.attributes:
            value = _attribute_value(record, attr)
            if value is None:
                continue
            if attr.child_entity is not None and isinstance(value, list):
                child_records = cast(Sequence[Mapping[str, object]], value)
                yield from _walk_records(
                    attr.child_entity, child_records, catalog_by_id
                )
            else:
                yield (entity, attr, value)


def _attribute_value(record: Mapping[str, object], attr: dc.Attribute) -> object:
    """The value of ``attr`` in ``record``, or ``None`` when absent.

    A dotted id (``profile.best``) names a value nested inside the
    singleton object it folds in, not a key spelled with a dot.
    """
    try:
        return json_data_model.pluck(record, attr.key_path)
    except KeyError:
        return None


def _fk_violation(entity: dc.Entity, attr: dc.Attribute, value: object) -> Diagnostic:
    """Build a Diagnostic for a dangling FK reference.

    The FROM-side attribute is named in fully-qualified form
    (``<entity>.<attr>``) so the diagnostic stays actionable even when
    the value carries no source location — the reader can grep the
    qualified name to locate the offending record.
    """
    assert attr.x_ref is not None
    qualified = attr.id if entity.id == dc.ROOT_ENTITY_ID else f"{entity.id}.{attr.id}"
    message = (
        f"x-ref {qualified} = {str(value)!r} has no match in "
        f"{attr.x_ref.entity}.{attr.x_ref.attribute}"
    )
    if isinstance(value, UserStr):
        location = value.location
        return Diagnostic(
            file=location.file,
            line=location.line,
            column=location.column,
            message=message,
            severity=DiagnosticSeverity.warning,
            source="x-ref-data",
        )
    return Diagnostic(
        file=None,
        line=None,
        column=None,
        message=message,
        severity=DiagnosticSeverity.warning,
        source="x-ref-data",
    )
