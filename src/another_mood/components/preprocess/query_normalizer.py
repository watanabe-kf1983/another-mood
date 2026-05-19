"""Query normalizer — the single sugar-to-canonical boundary.

User-facing YAML accepts shape sugar (bare-string flatten, single
mapping join, ``flatten: true`` shorthand) and omitted defaults; the
persisted ``__definition.queries`` carries the canonical mapping that
downstream consumers (``parse_query``, ``__meta_query`` template)
read.  Per-clause shape and defaults are documented on each helper.
"""

from collections.abc import Mapping, Sequence
from typing import cast


def normalize_query(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Expand sugar forms and fill defaults on one query record.

    ``raw`` is one query entry (carrying ``id``, ``from``, and any
    optional clauses).  The returned mapping has the same keys as
    ``raw`` plus all defaults required by the canonical form;
    clauses absent from ``raw`` stay absent in the output.
    """
    from_ = cast(str, raw["from"])
    out: dict[str, object] = {"id": raw["id"], "from": from_}
    if "flatten" in raw:
        out["flatten"] = normalize_flatten(raw["flatten"])
    if "join" in raw:
        out["join"] = normalize_join(raw["join"])
    if "where" in raw:
        out["where"] = raw["where"]
    if "grouped" in raw:
        out["grouped"] = normalize_grouped(
            cast(Mapping[str, object], raw["grouped"]), from_=from_
        )
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
    return {"of": name, "as": name, "preserve_empty": False}


def _flatten_entry_from_mapping(raw: Mapping[str, object]) -> Mapping[str, object]:
    of = cast(str, raw["of"])
    return {
        "of": of,
        "as": cast(str, raw.get("as", of)),
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
    as_ = cast(str, raw.get("as", to))
    out: dict[str, object] = {"to": to, "on": raw["on"], "as": as_}
    if "where" in raw:
        out["where"] = raw["where"]
    if "flatten" in raw:
        out["flatten"] = normalize_inline_flatten(raw["flatten"], as_)
    return out


def normalize_inline_flatten(raw: object, join_as: str) -> Mapping[str, object]:
    """Expand ``join[].flatten`` shorthand (``true`` or partial mapping) to object form.

    ``of:`` is fixed to ``join_as`` since the unwind target is always
    the just-attached array.
    """
    if raw is True:
        return {"of": join_as, "as": join_as, "preserve_empty": False}
    mapping = cast(Mapping[str, object], raw)
    return {
        "of": join_as,
        "as": cast(str, mapping.get("as", join_as)),
        "preserve_empty": cast(bool, mapping.get("preserve_empty", False)),
    }


def normalize_grouped(raw: Mapping[str, object], *, from_: str) -> Mapping[str, object]:
    """Normalize the ``grouped`` clause, filling the ``as`` default from ``from_``."""
    # ``from_.rsplit`` drops UserStr provenance (``str`` methods return
    # plain str), which is acceptable: the synthesized ``as`` is not a
    # catalog-validated identifier, so diagnostics never reference it.
    return {
        "by": cast(str, raw["by"]),
        "as": cast(str, raw.get("as", from_.rsplit(".", 1)[-1])),
    }


def normalize_select(
    raw: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Normalize the ``select`` clause, filling each entry's ``as`` default from ``item``."""
    return [
        {"item": cast(str, e["item"]), "as": cast(str, e.get("as", e["item"]))}
        for e in raw
    ]


def normalize_sort(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Normalize the ``sort`` clause, filling ``direction`` / ``missing`` defaults."""
    return {
        "by": cast(str, raw["by"]),
        "direction": cast(str, raw.get("direction", "asc")),
        "missing": cast(str, raw.get("missing", "last")),
    }
