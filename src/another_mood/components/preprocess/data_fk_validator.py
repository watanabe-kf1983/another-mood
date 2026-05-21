"""Data-level foreign-key integrity check.

For every property declared with ``x-ref``, verify that the actual
value appears in the target attribute's value set.  Run after content
normalization so the data is already in canonical ``[{"id": ..., ...}]``
shape, regardless of whether the user wrote a dict-pattern or an
explicit array.

Position info comes from the ``UserStr`` tag carried by each scalar
string value (set up by ``source_loader.parse_yaml``), so diagnostics
point at the originating YAML line/column.  When the value is not
UserStr-tagged (e.g. data was re-loaded from disk via ``typ='safe'``,
or constructed in memory), the diagnostic still names the offending
entity / attribute / value but the file/line/column fields stay None.

Each violation is returned as a :class:`Diagnostic` with
``severity=warning`` and ``source="x-ref-data"``.
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import cast

from another_mood.components.preprocess.source_loader import UserStr
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.diagnostic import Diagnostic, DiagnosticSeverity

#: Attribute types whose values can serve as FK targets.  Non-scalar
#: types (``object``, ``object[]``) carry dict / list values that are
#: not hashable into a target set, and could not match an x-ref value
#: anyway since the meta-schema constrains x-ref to ``type: string``.
_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})


def check_fk_data(
    catalog: Sequence[dc.Entity],
    data_by_entity: Mapping[str, Sequence[Mapping[str, object]]],
) -> Sequence[Diagnostic]:
    """Diagnose FK values with no match in the declared target set.

    ``catalog`` carries every entity (user + builtin, top-level +
    nested).  ``data_by_entity`` maps each top-level entity id to its
    list of normalized records; nested entities are reached by
    recursive descent through attributes whose ``child_entity`` is set.

    Only top-level entities can be FK targets per the schema spec, so
    the target index is built solely from records at the top.  The
    FROM-side walk covers every entity (top-level or nested), since
    ``x-ref`` may be declared on any property in the catalog.
    """
    catalog_by_id = {e.id: e for e in catalog}
    target_index = _build_target_index(catalog_by_id, data_by_entity)
    return [
        _fk_violation(entity, attr, value)
        for entity_id, records in data_by_entity.items()
        for entity, attr, value in _walk_records(entity_id, records, catalog_by_id)
        if attr.x_ref is not None
        and value
        not in target_index.get((attr.x_ref.entity, attr.x_ref.attribute), frozenset())
    ]


def _build_target_index(
    catalog_by_id: Mapping[str, dc.Entity],
    data_by_entity: Mapping[str, Sequence[Mapping[str, object]]],
) -> Mapping[tuple[str, str], frozenset[object]]:
    """Build ``(target_entity_id, target_attribute_id) -> value set``.

    Only top-level entities are valid FK targets; nested entities are
    skipped.  Missing values (``None`` / absent key) are excluded so
    optional attributes do not pollute the set with an implicit null.
    """
    index: dict[tuple[str, str], frozenset[object]] = {}
    for entity_id, records in data_by_entity.items():
        entity = catalog_by_id.get(entity_id)
        if entity is None or entity.parent_entity is not None:
            continue
        for attr in entity.item_type.attributes:
            if attr.type not in _SCALAR_TYPES:
                # Non-scalar attributes (singleton-flatten parents like
                # ``body`` / ``x_ref``, child-entity links) cannot be FK
                # targets and their dict/list values are unhashable.
                continue
            values = frozenset(
                rec[attr.id] for rec in records if rec.get(attr.id) is not None
            )
            index[(entity.id, attr.id)] = values
    return index


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
            value = record.get(attr.id)
            if value is None:
                continue
            if attr.child_entity is not None and isinstance(value, list):
                child_records = cast(Sequence[Mapping[str, object]], value)
                yield from _walk_records(
                    attr.child_entity, child_records, catalog_by_id
                )
            else:
                yield (entity, attr, value)


def _fk_violation(entity: dc.Entity, attr: dc.Attribute, value: object) -> Diagnostic:
    """Build a Diagnostic for a dangling FK reference.

    The FROM-side attribute is named in fully-qualified form
    (``<entity>.<attr>``) so the diagnostic stays actionable even when
    the value carries no source location — the reader can grep the
    qualified name to locate the offending record.
    """
    assert attr.x_ref is not None
    message = (
        f"x-ref {entity.id}.{attr.id} = {str(value)!r} has no match in "
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
