"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

import shutil
import sys
import traceback
from pathlib import Path

from reqs_builder.components.generator import template_engine
from reqs_builder.components.shared.json_data_model import load_yamls


def generate(views_dir: Path, templates_dir: Path, out_dir: Path) -> None:
    """Load views, render index.md template, and write output.

    On error, clears out_dir and writes an error page so the
    developer sees the problem in the browser instead of stale output.
    """
    try:
        views = load_yamls(views_dir)
        rendered = template_engine.render("index", templates_dir, views, out_dir)

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.md").write_text(rendered)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _write_error_page(out_dir, exc, traceback.format_exc())


def _write_error_page(out_dir: Path, exc: Exception, tb: str) -> None:
    """Replace output with a Markdown error page."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(_format_error(exc, tb))


def _format_error(exc: Exception, tb: str) -> str:
    lines = ["# Build Error\n"]
    location = _extract_location(exc)
    if location:
        lines.append(f"**{location}**\n")
    lines.append(f"**{type(exc).__name__}**: {exc}\n")
    lines.append(
        f"<details>\n<summary>Traceback</summary>\n\n```\n{tb}```\n\n</details>\n"
    )
    return "\n".join(lines)


def _extract_location(exc: Exception) -> str | None:
    """Extract template filename and line number from Jinja2 errors."""
    filename = getattr(exc, "filename", None)
    lineno = getattr(exc, "lineno", None)
    if filename and lineno:
        return f"{filename}, line {lineno}"
    return None
