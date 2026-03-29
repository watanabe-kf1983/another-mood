"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.errors import collect_report, error_propagation
from reqs_builder.components.shared.json_data_model import load_yamls


@Component(
    out_dir="out_dir", input_dirs=["data_dir", "templates_dir"], error_propagation=False
)
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Generate Markdown output, rendering errors as a page if present."""
    with error_propagation([data_dir, templates_dir], out_dir) as ok:
        if ok:
            data = load_yamls(data_dir)
            render("__root", data, out_dir, templates_dir=templates_dir)

    report = collect_report(out_dir)
    if report is not None and report["__build_report"].get("errors"):
        _clear_contents(out_dir)
        render("__build_report", report["__build_report"], out_dir)


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
