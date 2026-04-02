"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.build_report import BuildReport
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.errors import error_propagation
from reqs_builder.components.shared.json_data_model import load_yamls
import reqs_builder.context as ctx


@Component(out_dir="out_dir", error_propagation=False)
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Generate Markdown output, rendering errors as a page if present."""
    with error_propagation([data_dir], out_dir, stage="generate") as ok:
        if ok:
            data = load_yamls(data_dir)
            render("__root", data, out_dir, templates_dir=templates_dir)

    report = BuildReport.collect(out_dir)
    if report.has_errors():
        _clear_contents(out_dir)
        render("__build_report", report.to_data(), out_dir)

    _print_result(report.has_errors())


def _print_result(has_errors: bool) -> None:
    """Print user-facing build result with timestamp (watch mode only)."""
    if not ctx.watch_mode:
        return
    timestamp = datetime.now().strftime("%H:%M:%S")
    if has_errors:
        print(f"Files updated, but document build failed at {timestamp}.", flush=True)
    else:
        print(
            f"Files updated, and document successfully built at {timestamp}.",
            flush=True,
        )


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
