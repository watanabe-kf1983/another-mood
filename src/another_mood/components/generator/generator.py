"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.

See: dev-docs/contents/internal/components/generator.md
"""

import math
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from jinja2 import Undefined

from another_mood.components.shared.query import From, Record
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    data = load_model(data_dir)
    data["__views"] = [{k: v for k, v in data.items() if k != "__views"}]
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
    (out_dir / "index.md").write_text(rendered)


def _query_from(parents: Sequence[Record], path: str) -> Sequence[Record]:
    """System-only Jinja2 filter: apply a Query DSL `from` clause to parents.

    Exposed to built-in templates (the `__root` render) only, not to user
    templates, until the built-in API stabilises. Mirrors the `from:`
    clause so a template can resolve an entity id (possibly dotted for
    nested entities) against the root parents list exposed as `__views`.
    Returns an empty sequence when the path is not populated (e.g. an
    entity is declared in the catalog but has no records yet);
    Composer-side strict evaluation still treats such cases as errors.
    """
    try:
        return From(path=path).apply(parents)
    except KeyError:
        return []


def _at(row: object, path: str) -> str:
    """System-only Jinja2 filter: navigate a dotted path through nested mappings.

    Exposed to built-in templates only (see `_query_from`). Missing keys,
    None, and Undefined collapse to empty string. Leaf values are
    stringified (Python repr for lists/mappings); GFM escaping is left to
    the caller via Jinja2's `replace` filter.
    """
    value: object = row
    for part in path.split("."):
        if not isinstance(value, Mapping):
            return ""
        value = cast(Mapping[str, object], value).get(part)
        if value is None:
            return ""
    if isinstance(value, Undefined):
        return ""
    return str(value)


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
    "query_from": _query_from,
    "at": _at,
    "to_yaml": _to_yaml,
}
