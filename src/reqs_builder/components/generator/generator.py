"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.generator.template_engine import TemplateEngine
from reqs_builder.components.shared.json_data_model import load_yamls


def generate(data_dir: Path, templates_dir: Path, out_dir: Path) -> None:
    """Load data, render through built-in root template, and write output.

    On error, renders via the built-in error template so the developer
    sees the problem in the browser instead of stale output.
    """
    try:
        data = load_yamls(data_dir)
        rendered = _render(data, templates_dir, out_dir)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        rendered = _render(_errors_data(exc), templates_dir, out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered)


def _render(data: Mapping[str, object], templates_dir: Path, out_dir: Path) -> str:
    if "__errors" in data:
        return TemplateEngine(out_dir).render("__errors", data)
    return TemplateEngine(out_dir, templates_dir=templates_dir).render("__root", data)


def _errors_data(exc: Exception) -> dict[str, list[dict[str, str]]]:
    source = _extract_location(exc) or ""
    return {
        "__errors": [
            {
                "source": source,
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        ]
    }


def _extract_location(exc: Exception) -> str | None:
    """Extract template filename and line number from Jinja2 errors."""
    filename = getattr(exc, "filename", None)
    lineno = getattr(exc, "lineno", None)
    if filename and lineno:
        return f"{filename}, line {lineno}"
    return None
