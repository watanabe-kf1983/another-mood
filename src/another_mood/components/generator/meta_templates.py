"""Built-in meta templates and their system-only Jinja2 filters."""

import math
from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from itertools import chain, pairwise
from pathlib import Path
from typing import Any, cast

import yaml
from jinja2 import Undefined

from another_mood.components.shared.json_data_model import pluck

BUILT_IN_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates")
)


def _pluck(row: object, key_path: str) -> object:
    """Jinja2 filter wrapper around :func:`pluck`.

    Missing keys and broken intermediate steps yield Jinja2's
    ``Undefined``, which renders as the empty string under the standard
    Undefined contract and is falsy for ``or []`` / ``length``.
    """
    if not isinstance(row, Mapping):
        return Undefined()
    try:
        return pluck(cast(Mapping[str, object], row), key_path)
    except KeyError:
        return Undefined()


def _walk_entity(
    views: object,
    entity_id: str,
    entities: Sequence[Mapping[str, object]],
) -> object:
    """Collect all rows of ``entity_id`` (root or descendant) from
    the ``views`` mapping.

    Descent for child entities follows the catalog's ``parent_entity``
    chain rather than parsing the dotted id, so singleton-traversed
    paths like ``__definition.entities.item_type.attributes`` resolve
    via :func:`pluck`'s dotted lookup. Missing root key or absent
    intermediate keys collapse to an empty list — the ``{% if rows %}``
    guard in built-in templates renders ``(no records)`` either way.
    """
    if not isinstance(views, Mapping):
        return Undefined()
    by_id = {cast(str, e["id"]): e for e in entities}
    ancestors = _ancestor_chain(entity_id, by_id)
    rows: Sequence[object] = _safe_pluck(
        cast(Mapping[str, object], views), ancestors[0]
    )
    for parent_id, child_id in pairwise(ancestors):
        suffix = child_id.removeprefix(parent_id + ".")
        rows = list(
            chain.from_iterable(
                _safe_pluck(row, suffix)
                for row in cast(Sequence[Mapping[str, object]], rows)
            )
        )
    return rows


def _ancestor_chain(
    entity_id: str, by_id: Mapping[str, Mapping[str, object]]
) -> Sequence[str]:
    """Walk ``parent_entity`` links upward, returning ids root-first."""
    chain_: list[str] = []
    current: str | None = entity_id
    while current is not None:
        chain_.insert(0, current)
        current = cast("str | None", by_id[current].get("parent_entity"))
    return chain_


def _safe_pluck(row: Mapping[str, object], key_path: str) -> Sequence[object]:
    """``pluck`` returning ``[]`` for missing keys, list-wrapping scalars."""
    try:
        value = pluck(row, key_path)
    except KeyError:
        return []
    if isinstance(value, list):
        return cast(Sequence[object], value)
    return [value]


def _to_yaml(value: object, flow: bool = False) -> str:
    """Jinja2 filter: dump a value as YAML.

    Built-in templates use this to render arbitrary Mapping[str, object]
    fields (e.g. Attribute.metadata, Attribute.validation) without
    enumerating known keys. Pass ``flow=True`` for single-line flow style
    suitable for Markdown table cells. Returns an empty string for
    None/Undefined.
    """
    if value is None or isinstance(value, Undefined):
        return ""
    # Disable PyYAML's soft line-wrap in flow mode — wrapping inserts
    # newlines that break the surrounding Markdown table row.
    width = math.inf if flow else 80
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=flow,
        sort_keys=False,
        width=width,
    ).rstrip()


SYSTEM_FILTERS: Mapping[str, Callable[..., Any]] = {
    "pluck": _pluck,
    "to_yaml": _to_yaml,
    "walk_entity": _walk_entity,
}
