"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.

See: dev-docs/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Callable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from another_mood.components.generator.data_tree import wrap_tree
from another_mood.components.generator.meta_templates import (
    META_TEMPLATES_DIR,
    META_TEMPLATES_FILTERS,
)
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model

_BUILD_REPORT_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "build_report")
)

_NO_FILTERS: Mapping[str, Callable[..., Any]] = {}


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    data = wrap_tree(load_model(data_dir))
    data["__views"] = {k: v for k, v in data.items() if k != "__views"}
    render(
        "__root.md",
        META_TEMPLATES_DIR,
        data,
        out_dir,
        filters=META_TEMPLATES_FILTERS,
    )
    render("index.md", templates_dir, data, out_dir / "reports")


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
                    "__warnings.md",
                    _BUILD_REPORT_TEMPLATES_DIR,
                    {"diagnostics": [d.to_data() for d in warnings]},
                    ctx.out / "__warnings",
                )
                _append_warnings_link(ctx.out / "index.md", len(warnings))
        else:
            report = BuildReport.collect(data_dir / "reports")
            render(
                "__build_failure.md",
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
) -> None:
    """Render a template and write the result to out_dir/index.md."""
    rendered = TemplateEngine(
        out_dir,
        templates_dir=templates_dir,
        filters=filters,
    ).render(template_name, data)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered, encoding="utf-8")
