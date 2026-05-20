"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.

See: dev-docs/contents/internal/components/generator.md
"""

import math
import shutil
from collections.abc import Callable, Mapping, Sequence
from itertools import chain, pairwise
from pathlib import Path
from typing import Any, cast

import yaml
from jinja2 import Undefined

from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model, pluck


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    data = load_model(data_dir)
    data["__views"] = {k: v for k, v in data.items() if k != "__views"}
    render("__root", data, out_dir, filters=_FILTERS)
    render("__reports", data, out_dir / "reports", templates_dir=templates_dir)


@Component(out_dir="out_dir", upstream_dirs=["data_dir"], error_propagation=False)
def reconcile(data_dir: Path, *, out_dir: Path) -> None:
    """Reconcile Generator output with the propagated BuildReport.

    No upstream errors: pass Generator's data through unchanged.
    Upstream errors: render a __build_failure page in its place.
    """
    with error_propagation([data_dir], out_dir, component="reconcile") as data_dirs:
        if data_dirs is not None:
            shutil.copytree(data_dirs.upstreams[0], data_dirs.out, dirs_exist_ok=True)
        else:
            report = BuildReport.collect(data_dir / "reports")
            render("__build_failure", report.to_data(), out_dir / "data")


def render(
    template_name: str,
    data: Mapping[str, object],
    out_dir: Path,
    *,
    templates_dir: Path | None = None,
    filters: Mapping[str, Callable[..., Any]] | None = None,
) -> None:
    """Render a template and write the result to out_dir/index.md."""
    rendered = TemplateEngine(
        out_dir, templates_dir=templates_dir, filters=filters
    ).render(template_name, data)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered, encoding="utf-8")


def _pluck(row: object, key_path: str) -> object:
    """System-only Jinja2 filter wrapper around :func:`pluck`.

    Exposed to built-in templates only, until the built-in API
    stabilises. Missing keys and broken intermediate steps yield
    Jinja2's `Undefined`, which renders as the empty string under the
    standard Undefined contract and is falsy for `or []` / `length`.
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
    """System-only Jinja2 filter: collect all rows of ``entity_id``
    (root or descendant) from the ``views`` mapping.

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


def _mermaid_class_id(entity_id: object) -> str:
    """System-only Jinja2 filter: turn a catalog entity id into a
    Mermaid classDiagram-safe identifier.

    Catalog ids carry dots when a parent walk crosses entity boundaries
    (``artists.members``, ``__definition.entities``).  Mermaid's
    classDiagram parser treats unquoted dots as namespace separators, so
    the dotted id cannot be used directly as a ``class`` name.  Replace
    ``.`` with ``_`` to alias the id; templates pass the original id as
    a label (``class artists_members["artists.members"]``) so the
    rendered diagram still shows the canonical id to readers.

    Catalog ids are constrained to ASCII identifier characters plus
    ``.``, so no other escaping is required here.
    """
    if not isinstance(entity_id, str):
        return ""
    return entity_id.replace(".", "_")


def _to_yaml(value: object, flow: bool = False) -> str:
    """System-only Jinja2 filter: dump a value as YAML.

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


_FILTERS: Mapping[str, Callable[..., Any]] = {
    "pluck": _pluck,
    "to_yaml": _to_yaml,
    "walk_entity": _walk_entity,
    "mermaid_class_id": _mermaid_class_id,
}
