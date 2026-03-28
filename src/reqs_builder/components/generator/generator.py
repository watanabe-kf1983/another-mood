"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.atomic_write import atomic_write
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.errors import collect_errors, error_propagation
from reqs_builder.components.shared.json_data_model import load_yamls


@Component(
    out_dir="out_dir", input_dirs=["data_dir", "templates_dir"], error_propagation=False
)
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Generate Markdown output, rendering errors as a page if present."""
    with atomic_write(out_dir) as od:
        with error_propagation([data_dir, templates_dir], od) as ok:
            if ok:
                data = load_yamls(data_dir)
                render("__root", data, od, templates_dir=templates_dir)

    errors = collect_errors(out_dir)
    if errors is not None:
        with atomic_write(out_dir) as od:
            render("__errors", errors, od)


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
