"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Mapping
from pathlib import Path

from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.build_report import BuildReport
from another_mood.components.shared.component import Component
from another_mood.components.shared.errors import error_propagation
from another_mood.components.shared.json_data_model import load_yamls


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    data = load_yamls(data_dir)
    render("__root", data, out_dir, templates_dir=templates_dir)
    render("__meta_root", data, out_dir / "__reference")


@Component(out_dir="out_dir", upstream_dirs=["data_dir"], error_propagation=False)
def reconcile(data_dir: Path, *, out_dir: Path) -> None:
    """Reconcile Generator output with the propagated BuildReport.

    No upstream errors: pass Generator's data through unchanged.
    Upstream errors: render a __build_report page in its place.
    """
    with error_propagation([data_dir], out_dir, component="reconcile") as data_dirs:
        if data_dirs is not None:
            shutil.copytree(data_dirs.upstreams[0], data_dirs.out, dirs_exist_ok=True)
        else:
            report = BuildReport.collect(data_dir / "reports")
            render("__build_report", report.to_data(), out_dir / "data")


def render(
    template_name: str,
    data: Mapping[str, object],
    out_dir: Path,
    *,
    templates_dir: Path | None = None,
) -> None:
    """Render a template and write the result to out_dir/index.md."""
    rendered = TemplateEngine(out_dir, templates_dir=templates_dir).render(
        template_name, data
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered)
