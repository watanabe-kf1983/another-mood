"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.atomic_write import with_atomic_write
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.errors import errors_data
from reqs_builder.components.shared.json_data_model import load_yamls


@with_atomic_write
@Component(out_dir="out_dir", input_dirs=["data_dir", "templates_dir"])
def generate(data_dir: Path, templates_dir: Path, *, out_dir: Path) -> None:
    """Load data, render through built-in root template, and write output.

    On error, renders via the built-in error template so the developer
    sees the problem in the browser instead of stale output.
    """
    try:
        data = load_yamls(data_dir)
        rendered = _render(data, templates_dir, out_dir)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        rendered = _render(errors_data(exc), templates_dir, out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered)


def _render(data: Mapping[str, object], templates_dir: Path, out_dir: Path) -> str:
    if "__errors" in data:
        _clear_dir(out_dir)
        return TemplateEngine(out_dir).render("__errors", data)
    return TemplateEngine(out_dir, templates_dir=templates_dir).render("__root", data)


def _clear_dir(path: Path) -> None:
    """Remove all contents of a directory."""
    if path.exists():
        shutil.rmtree(path)
