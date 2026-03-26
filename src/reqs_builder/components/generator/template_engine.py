"""Template engine — Jinja2 rendering with section support.

Hides Jinja2 details behind a single `render` function.
"""

from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader

from reqs_builder.components.generator.page_writer import PageWriter
from reqs_builder.components.generator.section_extension import make_section_env


def render(
    template_name: str,
    templates_dir: Path,
    data: dict[str, Any],
    out_dir: Path,
) -> str:
    """Render a template with data and write section pages to out_dir."""

    def render_template(name: str, tdata: dict[str, Any]) -> str:
        return env.get_template(f"{name}.md").render(tdata)

    writer = PageWriter(out_dir=out_dir, render=render_template)
    env = make_section_env(writer)
    env.loader = FileSystemLoader(templates_dir)

    return env.get_template(f"{template_name}.md").render(data)
