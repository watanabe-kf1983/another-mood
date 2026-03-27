"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
import sys
import traceback
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.json_data_model import load_yamls


def generate(data_dir: Path, templates_dir: Path, out_dir: Path) -> None:
    """Load data, render through built-in root template, and write output.

    On error, clears out_dir and renders via the built-in error template
    so the developer sees the problem in the browser instead of stale output.
    """
    try:
        data = load_yamls(data_dir)
        engine = TemplateEngine(out_dir, templates_dir=templates_dir)
        rendered = engine.render(data)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        data = {"__errors": [_exception_to_error(exc)]}
        engine = TemplateEngine(out_dir)
        rendered = engine.render(data)
        if out_dir.exists():
            shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered)


def _exception_to_error(exc: Exception) -> dict[str, str]:
    source = _extract_location(exc) or ""
    return {
        "source": source,
        "message": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc(),
    }


def _extract_location(exc: Exception) -> str | None:
    """Extract template filename and line number from Jinja2 errors."""
    filename = getattr(exc, "filename", None)
    lineno = getattr(exc, "lineno", None)
    if filename and lineno:
        return f"{filename}, line {lineno}"
    return None
