"""Built-in meta templates and their system-only Jinja2 filters."""

import math
from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from itertools import chain, pairwise
from pathlib import Path
from typing import Any, cast

import yaml
from jinja2 import Undefined

from another_mood.components.generator.edition import Edition
from another_mood.components.shared import json_data_model

META_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "meta")
)

META_EDITION = Edition(
    file_per=("__entity_defs.item", "__entity_data.item", "__queries.item")
)
"""Fixed split policy for the meta render.

The meta diagnostics have no user ``reports.yaml``; their page split is
internal.  Each built-in query (``__entity_defs`` / ``__entity_data`` /
``__queries``) yields one result item per entity/query, and listing
the item object-type ids here routes those item nodes to their own
``{query}/{id}.md`` page via the ordinary ``page_path`` derivation."""


def pluck(row: object, key_path: str) -> object:
    """Jinja2 filter wrapper around :func:`json_data_model.pluck`.

    Missing keys and broken intermediate steps yield Jinja2's
    ``Undefined``, which renders as the empty string under the standard
    Undefined contract and is falsy for ``or []`` / ``length``.
    """
    if not isinstance(row, Mapping):
        return Undefined()
    try:
        return json_data_model.pluck(cast(Mapping[str, object], row), key_path)
    except KeyError:
        return Undefined()


def walk_entity(
    views: object,
    entity_id: str,
    entities: Sequence[Mapping[str, object]],
) -> object:
    """Collect all rows of ``entity_id`` (root or descendant) from
    the ``views`` mapping.

    Descent for child entities follows the catalog's ``parent_entity``
    chain rather than parsing the dotted id, so singleton-traversed
    paths like ``__definition.entities.item_type.attributes`` resolve
    via :func:`json_data_model.pluck`'s dotted lookup. Missing root key
    or absent intermediate keys collapse to an empty list — the
    ``{% if rows %}`` guard in built-in templates renders ``(no records)``
    either way.
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


def to_yaml(value: object, flow: bool = False) -> str:
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
    dumper = _InlineDumper if flow else _Dumper
    return yaml.dump(
        value,
        Dumper=dumper,
        allow_unicode=True,
        default_flow_style=flow,
        sort_keys=False,
        width=width,
    ).rstrip()


META_TEMPLATES_FILTERS: Mapping[str, Callable[..., Any]] = {
    "pluck": pluck,
    "to_yaml": to_yaml,
    "walk_entity": walk_entity,
}


# ── walk_entity helpers ──────────────────────────────────────────────


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
    """``json_data_model.pluck`` returning ``[]`` for missing keys,
    list-wrapping scalars."""
    try:
        value = json_data_model.pluck(row, key_path)
    except KeyError:
        return []
    if isinstance(value, list):
        return cast(Sequence[object], value)
    return [value]


# ── to_yaml dumpers and representers ─────────────────────────────────


class _Dumper(yaml.SafeDumper):
    """SafeDumper that accepts ``dict`` / ``list`` subclasses.

    Generator wraps the data tree into :class:`MappingNode` /
    :class:`ArrayNode` (see ``data_tree.py``) so templates can walk
    parent references.  SafeDumper rejects subclasses by default;
    the multi-representer registrations below make any subclass
    render as its native ``dict`` / ``list`` form.
    """


class _InlineDumper(yaml.SafeDumper):
    """SafeDumper for one-source-line output contexts.

    Used when the YAML result is interpolated into a single-line
    context — a Markdown table cell as inline code, etc.  PyYAML's
    default str representer renders newline-containing scalars as
    single-quoted folded form that spans multiple source lines,
    which breaks such embedding.  This variant forces double-quoted
    style so embedded newlines emit as ``\\n`` escapes and the
    output stays on one line.

    Carries the same ``dict`` / ``list`` subclass support as
    :class:`_Dumper` (registered explicitly below).
    """


def _inline_str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = '"' if "\n" in data else None
    return dumper.represent_scalar(  # pyright: ignore[reportUnknownMemberType]
        "tag:yaml.org,2002:str", data, style=style
    )


def _represent_dict_subclass(
    dumper: yaml.SafeDumper, data: Mapping[str, object]
) -> yaml.MappingNode:
    return dumper.represent_dict(data)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def _represent_list_subclass(
    dumper: yaml.SafeDumper, data: Sequence[object]
) -> yaml.SequenceNode:
    return dumper.represent_list(data)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


_Dumper.add_multi_representer(dict, _represent_dict_subclass)
_Dumper.add_multi_representer(list, _represent_list_subclass)

_InlineDumper.add_multi_representer(dict, _represent_dict_subclass)
_InlineDumper.add_multi_representer(list, _represent_list_subclass)
_InlineDumper.add_representer(str, _inline_str_representer)
