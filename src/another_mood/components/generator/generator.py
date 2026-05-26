"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.

See: dev-docs/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Mapping
from pathlib import Path

from another_mood.components.generator.meta_templates import (
    BUILT_IN_TEMPLATES_DIR,
    SYSTEM_FILTERS,
)
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    data = load_model(data_dir)
    data["__views"] = {k: v for k, v in data.items() if k != "__views"}
    render("__root.md", data, out_dir)
    render("__reports.md", data, out_dir / "reports", templates_dir=templates_dir)


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
                    {"diagnostics": [d.to_data() for d in warnings]},
                    ctx.out / "__warnings",
                )
                _append_warnings_link(ctx.out / "index.md", len(warnings))
        else:
            report = BuildReport.collect(data_dir / "reports")
            render("__build_failure.md", report.to_data(), out_dir / "data")


def _append_warnings_link(index_md: Path, count: int) -> None:
    """Append a short ``## Warnings`` block linking to the warnings page."""
    label = f"{count} warning{'' if count == 1 else 's'}"
    with index_md.open("a", encoding="utf-8") as f:
        f.write(f"\n## Warnings\n\n{label} — [view](__warnings/)\n")


def render(
    template_name: str,
    data: Mapping[str, object],
    out_dir: Path,
    *,
    templates_dir: Path | None = None,
) -> None:
    """Render a template and write the result to out_dir/index.md."""
    templates_dirs: list[Path] = [BUILT_IN_TEMPLATES_DIR]
    if templates_dir is not None:
        templates_dirs.append(templates_dir)
    rendered = TemplateEngine(
        out_dir,
        templates_dirs=templates_dirs,
        filters=SYSTEM_FILTERS,
    ).render(template_name, data)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered, encoding="utf-8")
