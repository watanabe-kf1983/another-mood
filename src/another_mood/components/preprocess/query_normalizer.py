"""Query normalizer — the single sugar-to-canonical boundary.

User-facing YAML accepts shape sugar (bare-string flatten, single
mapping join, ``flatten: true`` shorthand, ``where``'s field-keyed
predicates) and omitted defaults; the persisted ``__definition.views``
carries the canonical mapping that downstream consumers
(``parse_query``, ``__view_defs`` template) read.  Per-clause shape and
defaults are documented on each helper.

A dot in a path is sugar too — it lets a nested field be read or
written on one YAML line — so it is resolved here, into the segments
the canonical form carries.  The ``__view_defs`` template spells the
dot back for display, except in ``where``, which it shows in its
canonical form: that page shows how a view resolved, and spelling a
predicate tree back would mean inverting this module.
"""

from collections.abc import Mapping, Sequence
from typing import cast

from another_mood.components.shared.user_source.source_loader import UserStr


def split_path(name: str) -> tuple[str, ...]:
    """Resolve a dotted path into its segments.

    ``str`` methods drop a :class:`UserStr`'s location, so each segment
    is retagged with it — a diagnostic anchored on any segment still
    points at the line the whole path was written on.
    """
    segments = name.split(".")
    if isinstance(name, UserStr):
        return tuple(UserStr(segment, name.location) for segment in segments)
    else:
        return tuple(segments)


def normalize_query(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Expand sugar forms and fill defaults on one query record.

    ``raw`` is one query entry (carrying ``id``, ``from``, and any
    optional clauses).  The returned mapping has the same keys as
    ``raw`` plus all defaults required by the canonical form;
    clauses absent from ``raw`` stay absent in the output.
    """
    out: dict[str, object] = {"id": raw["id"], "from": cast(str, raw["from"])}
    if "flatten" in raw:
        out["flatten"] = normalize_flatten(raw["flatten"])
    if "join" in raw:
        out["join"] = normalize_join(raw["join"])
    if "where" in raw:
        out["where"] = normalize_where(cast(Mapping[str, object], raw["where"]))
    if "grouped" in raw:
        out["grouped"] = normalize_grouped(cast(Mapping[str, object], raw["grouped"]))
    if "select" in raw:
        out["select"] = normalize_select(
            cast(Sequence[Mapping[str, object]], raw["select"])
        )
    if "sort" in raw:
        out["sort"] = normalize_sort(cast(Mapping[str, object], raw["sort"]))
    return out


def normalize_flatten(raw: object) -> list[Mapping[str, object]]:
    """Normalize the ``flatten`` clause to a list of object-form entries."""
    if isinstance(raw, str):
        return [_flatten_entry_from_shorthand(raw)]
    if isinstance(raw, Mapping):
        return [_flatten_entry_from_mapping(cast(Mapping[str, object], raw))]
    if isinstance(raw, Sequence):
        return [
            _flatten_entry_from_shorthand(entry)
            if isinstance(entry, str)
            else _flatten_entry_from_mapping(cast(Mapping[str, object], entry))
            for entry in cast(Sequence[object], raw)
        ]
    raise TypeError(
        f"flatten clause must be a string, mapping, or list; got {type(raw).__name__}"
    )


def _flatten_entry_from_shorthand(name: str) -> Mapping[str, object]:
    return {
        "of": split_path(name),
        "as": split_path(name),
        "preserve_empty": False,
    }


def _flatten_entry_from_mapping(raw: Mapping[str, object]) -> Mapping[str, object]:
    of = cast(str, raw["of"])
    return {
        "of": split_path(of),
        "as": split_path(cast(str, raw.get("as", of))),
        "preserve_empty": cast(bool, raw.get("preserve_empty", False)),
    }


def normalize_join(raw: object) -> list[Mapping[str, object]]:
    """Normalize the ``join`` clause to a list of object-form entries."""
    if isinstance(raw, Mapping):
        return [_normalize_join_entry(cast(Mapping[str, object], raw))]
    if isinstance(raw, Sequence):
        return [
            _normalize_join_entry(cast(Mapping[str, object], entry))
            for entry in cast(Sequence[object], raw)
        ]
    raise TypeError(f"join clause must be a mapping or list; got {type(raw).__name__}")


def _normalize_join_entry(raw: Mapping[str, object]) -> Mapping[str, object]:
    to = cast(str, raw["to"])
    as_ = split_path(cast(str, raw.get("as", to)))
    on = cast(Mapping[str, str], raw["on"])
    out: dict[str, object] = {
        "to": to,
        "on": {"left": split_path(on["left"]), "right": split_path(on["right"])},
        "as": as_,
    }
    if "where" in raw:
        out["where"] = normalize_where(cast(Mapping[str, object], raw["where"]))
    if "flatten" in raw:
        out["flatten"] = normalize_inline_flatten(raw["flatten"], as_)
    return out


def normalize_inline_flatten(
    raw: object, join_as: Sequence[str]
) -> Mapping[str, object]:
    """Expand ``join[].flatten`` shorthand (``true`` or partial mapping) to object form.

    ``of:`` is fixed to ``join_as`` -- the path the join just wrote its
    right side to -- since the unwind target is always that array.
    """
    target = tuple(join_as)
    if raw is True:
        return {"of": target, "as": target, "preserve_empty": False}
    mapping = cast(Mapping[str, object], raw)
    as_ = mapping.get("as")
    return {
        "of": target,
        "as": target if as_ is None else split_path(cast(str, as_)),
        "preserve_empty": cast(bool, mapping.get("preserve_empty", False)),
    }


def normalize_where(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Expand one ``where`` node into the predicate tree, a node per predicate.

    A field predicate becomes ``{field, operator, target}`` -- keyed by
    role rather than by field name, so the field can be a path of
    segments.  A scalar is ``eq``; an operator bundle (``{gt: 10, lt:
    20}``) and several keys on one node each become an ``and`` of their
    parts, unwrapped when there is just one.
    """
    clauses = [_where_entry(key, value) for key, value in raw.items()]
    return clauses[0] if len(clauses) == 1 else {"and": clauses}


def _where_entry(key: str, value: object) -> Mapping[str, object]:
    if key in ("and", "or"):
        return {
            key: [
                normalize_where(cast(Mapping[str, object], child))
                for child in cast(Sequence[object], value)
            ]
        }
    elif key == "not":
        return {"not": normalize_where(cast(Mapping[str, object], value))}
    else:
        return _field_predicate(split_path(key), value)


def _field_predicate(field: Sequence[str], value: object) -> Mapping[str, object]:
    bundle = (
        cast(Mapping[str, object], value)
        if isinstance(value, Mapping)
        else {"eq": value}
    )
    clauses = [
        {"field": field, "operator": operator, "target": target}
        for operator, target in bundle.items()
    ]
    return clauses[0] if len(clauses) == 1 else {"and": clauses}


def normalize_grouped(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Normalize the ``grouped`` clause.  Both keys are schema-required.

    ``by`` is read as a path and the key value is written back at that
    same path.
    """
    return {
        "by": split_path(cast(str, raw["by"])),
        "as": split_path(cast(str, raw["as"])),
    }


def normalize_select(
    raw: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Normalize the ``select`` clause, filling each entry's ``as`` default from ``item``."""
    return [
        {
            "item": split_path(cast(str, e["item"])),
            "as": split_path(cast(str, e.get("as", e["item"]))),
        }
        for e in raw
    ]


def normalize_sort(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Normalize the ``sort`` clause, filling ``direction`` / ``missing`` defaults."""
    return {
        "by": split_path(cast(str, raw["by"])),
        "direction": cast(str, raw.get("direction", "asc")),
        "missing": cast(str, raw.get("missing", "last")),
    }
