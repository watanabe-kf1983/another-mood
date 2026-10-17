# ``_meta`` is a node field under the reserved ``_`` prefix (see data_tree.py),
# not a Python-protected attribute.
# pyright: reportPrivateUsage=false
"""Built-in meta templates and their system-only template filters."""

import math
from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from itertools import chain, pairwise
from pathlib import Path
from typing import cast

import yaml

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.edition import Edition, PagingPolicy
from another_mood.components.generator.inert import (
    InertArray,
    InertValue,
    ensure_inert,
)
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared import json_data_model
from another_mood.components.shared.json_data_model import KeyPath

META_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "meta")
)


def pluck(row: object, attribute_id: str) -> InertValue:
    """Template filter: the value of the attribute ``attribute_id`` in ``row``.

    Missing keys and broken intermediate steps yield ``None``, which renders as
    nothing and is falsy — a caller needing a container guards with ``or []``.
    """
    if not isinstance(row, Mapping):
        return None
    try:
        value = json_data_model.pluck(
            cast(Mapping[str, object], row), dc.Attribute.split_id(attribute_id)
        )
    except KeyError:
        return None
    # The shared pluck is typed to return `object`; re-marshal to inert.
    return ensure_inert(value)


def walk_entity(
    views: object,
    entity_id: str,
    entities: Sequence[Mapping[str, object]],
) -> InertArray:
    """Collect all rows of ``entity_id`` (root or descendant) from
    the ``views`` mapping.

    Descent for child entities follows the catalog's ``parent_entity``
    chain rather than parsing the dotted id, which does not tell where the
    arrays are; each step reads the attribute id the child extends its
    parent's id by, singletons included (``item_type.attributes`` under
    ``__definition.entities``). ``views`` itself is the one row the walk
    starts from, so the top-level step is the same pluck as every other
    step. A non-mapping ``views`` or an absent key at any step collapses
    to an empty list — the ``{% if rows %}`` guard in built-in templates
    renders ``(no records)`` either way.
    """
    if not isinstance(views, Mapping):
        return InertArray()
    by_id = {cast(str, e["id"]): e for e in entities}
    ancestors = _ancestor_chain(entity_id, by_id)
    rows: Sequence[InertValue] = [cast(InertValue, views)]
    for parent_id, child_id in pairwise(ancestors):
        suffix = dc.Attribute.split_id(dc.attribute_suffix(parent_id, child_id))
        rows = list(
            chain.from_iterable(
                _safe_pluck(row, suffix)
                for row in cast(Sequence[Mapping[str, object]], rows)
            )
        )
    return InertArray(rows)


def to_yaml(value: object, flow: bool = False) -> str:
    """Template filter: dump a value as YAML.

    Built-in templates use this to render arbitrary Mapping[str, object]
    fields (e.g. Attribute.metadata, Attribute.validation) without
    enumerating known keys. Pass ``flow=True`` for single-line flow style
    suitable for Markdown table cells. Returns an empty string for an
    absent value.
    """
    if value is None:
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


def anchor_path(a: object) -> str | None:
    """Template filter: a node's anchor path as a string — the template-side
    reader of ``_meta.anchor_path``.

    A value that is not a node has no address and yields ``None``, which
    renders as nothing: the same rows reach this filter whether or not they
    resolved to anchored data.
    """
    if isinstance(a, Node):
        return a._meta.anchor_path
    else:
        return None


# Where a new helper goes: format-specific, position-aware normalisation
# belongs in the format's own tables (md.py's MD_GLOBALS / MD_FILTERS); a
# format-neutral helper that only the meta templates need (catalog traversal,
# shaping) belongs here.  Mixing the two would make every added output format
# re-register these, and expose them to user templates.
META_TEMPLATES_FILTERS: Mapping[str, Callable[..., InertValue]] = {
    "anchor_path": anchor_path,
    "pluck": pluck,
    "to_yaml": to_yaml,
    "walk_entity": walk_entity,
}


META_EDITION = Edition(
    paging=PagingPolicy(
        (
            "__root_def.item[]",
            "__root_data.item[]",
            "__entity_defs.item",
            "__view_defs.item",
            "__data.item",
        )
    ),
    name="__db",
    templates_dir=META_TEMPLATES_DIR,
    extra_filters=META_TEMPLATES_FILTERS,
    mirror_blobs=False,
)
"""The built-in meta edition — the database self-description, mounted at
``__db/`` and rendered from the meta templates with the system-only
``extra_filters`` above (mount and ``__`` naming: paging-spec).

``file_per`` is the fixed internal page split: with no user ``reports.yaml``,
listing the built-in views' item ids routes each view's result to its own
``{view}/{id}.md`` page via the ordinary ``page_path`` derivation.  The
root's views list their array id instead, so the one-record result lands
on a single ``{view}.md`` page."""


# ── walk_entity helpers ──────────────────────────────────────────────


def _ancestor_chain(
    entity_id: str, by_id: Mapping[str, Mapping[str, object]]
) -> Sequence[str]:
    """Walk ``parent_entity`` links upward, returning ids root-first."""
    chain_: list[str] = []
    current = entity_id
    while current != dc.ROOT_ENTITY_ID:
        chain_.insert(0, current)
        current = cast(str, by_id[current]["parent_entity"])
    return [dc.ROOT_ENTITY_ID, *chain_]


def _safe_pluck(row: Mapping[str, object], key_path: KeyPath) -> Sequence[InertValue]:
    """``json_data_model.pluck`` returning ``[]`` for missing keys,
    list-wrapping scalars."""
    try:
        value = json_data_model.pluck(row, key_path)
    except KeyError:
        return []
    inert = ensure_inert(value)
    if isinstance(inert, InertArray):
        return inert
    return [inert]


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
