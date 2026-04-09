"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.build_report import BuildReport
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.errors import error_propagation
from reqs_builder.components.shared.json_data_model import load_yamls


@Component(out_dir="out_dir", error_propagation=False)
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Generate Markdown output, rendering errors as a page if present."""
    with error_propagation([data_dir], out_dir, component="generate") as data_dirs:
        if data_dirs is not None:
            data = load_yamls(data_dirs.upstreams[0])
            render("__root", data, data_dirs.out, templates_dir=templates_dir)
            render("__meta_root", data, data_dirs.out / "__reference")

    report = BuildReport.collect(out_dir / "reports")
    if report.has_errors():
        data_out = out_dir / "data"
        _clear_contents(data_out)
        render("__build_report", report.to_data(), data_out)
        report.write(out_dir / "reports")


def _clear_contents(directory: Path) -> None:
    """Remove all children of *directory* while keeping the directory itself."""
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


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
