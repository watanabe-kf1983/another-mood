"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.
"""

import shutil
from collections.abc import Callable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any, cast

from another_mood.components.generator.data_tree import MappingNode, build_node_map
from another_mood.components.generator.data_tree_filters import make_data_tree_filters
from another_mood.components.generator.edition import (
    PagingPolicy,
    load_editions,
)
from another_mood.components.generator.meta_templates import META_EDITION
from another_mood.components.generator.output_formats.md import (
    MD,
    MD_FILTERS,
    MD_GLOBALS,
    make_link_filters,
)
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model

_BUILD_REPORT_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "build_report")
)

_COVER_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "cover")
)

_NO_FILTERS: Mapping[str, Callable[..., Any]] = {}


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(
    data_dir: Path,
    templates_dir: Path,
    reports_file: Path,
    project_name: str,
    *,
    out_dir: Path,
) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    user_editions = load_editions(reports_file, templates_dir)
    editions = (META_EDITION, *user_editions)

    # The root cover just lists the editions — no data model, so no filters.
    render(
        "index.md",
        _COVER_TEMPLATES_DIR,
        {"editions": editions, "project_name": project_name},
        out_dir,
    )

    # A page tree per edition, over the shared data model.
    model = load_model(data_dir)
    node_map = build_node_map(model)
    data = cast(MappingNode, node_map["/"])
    node_globals, node_filters = make_data_tree_filters(node_map)
    for edition in editions:
        render(
            edition.root_template,
            edition.templates_dir,
            data,
            out_dir / edition.dir_segment,
            filters={
                **edition.extra_filters,
                **node_filters,
                **make_link_filters(edition.paging, node_map),
            },
            globals=node_globals,
            paging=edition.paging,
        )


@Component(out_dir="out_dir", upstream_dirs=["data_dir"], error_propagation=False)
def reconcile(data_dir: Path, *, out_dir: Path) -> None:
    """Reconcile Generator output with the propagated BuildReport.

    No upstream errors: pass Generator's data through.  When the
    propagated report carries warning diagnostics, render a
    ``__warnings/`` page and link to it from ``index.md``.

    Upstream errors: render a __build_failure page in its place.
    """
    with error_propagation([data_dir], out_dir, component="reconcile") as ctx:
        if ctx is not None:
            shutil.copytree(ctx.upstreams[0], ctx.out, dirs_exist_ok=True)
            warnings = [
                d
                for d in BuildReport.collect(data_dir / "reports").diagnostics
                if d.severity == "warning"
            ]
            if warnings:
                render(
                    "warnings.md",
                    _BUILD_REPORT_TEMPLATES_DIR,
                    {"diagnostics": [d.to_data() for d in warnings]},
                    ctx.out / "__warnings",
                )
                _append_warnings_link(ctx.out / "index.md", len(warnings))
        else:
            report = BuildReport.collect(data_dir / "reports")
            render(
                "build_failure.md",
                _BUILD_REPORT_TEMPLATES_DIR,
                report.to_data(),
                out_dir / "data",
            )


def _append_warnings_link(index_md: Path, count: int) -> None:
    """Append a short ``## Warnings`` block linking to the warnings page."""
    label = f"{count} warning{'' if count == 1 else 's'}"
    with index_md.open("a", encoding="utf-8") as f:
        f.write(f"\n## Warnings\n\n{label} — [view](__warnings/)\n")


def render(
    template_name: str,
    templates_dir: Path,
    data: Mapping[str, object],
    out_dir: Path,
    *,
    filters: Mapping[str, Callable[..., Any]] = _NO_FILTERS,
    globals: Mapping[str, Callable[..., Any]] = _NO_FILTERS,
    paging: PagingPolicy = PagingPolicy(),
) -> None:
    """Render a template and write the result to out_dir/index.md.

    The md format's own helpers are injected here so every render gets them; the
    caller adds any edition / node-map-bound filters on top via ``filters``.
    ``paging`` drives ``{% mood_view %}`` split/inline (empty = inline all).
    """
    TemplateEngine(
        out_dir,
        templates_dir=templates_dir,
        output_format=MD,
        filters={**MD_FILTERS, **filters},
        globals={**MD_GLOBALS, **globals},
        paging=paging,
    ).render_to_file(template_name, data, Path("index.md"))
