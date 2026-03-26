"""Template engine — Jinja2 rendering with section support.

Hides Jinja2 details behind a single `render` function.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from reqs_builder.components.generator.page_writer import PageWriter
from reqs_builder.components.generator.section_extension import (
    make_section_env,
    set_processor,
)


def _render_template(env: Environment, name: str, data: dict[str, Any]) -> str:
    return env.get_template(f"{name}.md").render(data)


def render(
    template_name: str,
    templates_dir: Path,
    data: dict[str, Any],
    out_dir: Path,
) -> str:
    """Render a template with data and write section pages to out_dir."""
    env = make_section_env()
    env.loader = FileSystemLoader(templates_dir)

    writer = PageWriter(
        out_dir=out_dir,
        render=lambda name, tdata: _render_template(env, name, tdata),
    )
    set_processor(env, writer)

    return env.get_template(f"{template_name}.md").render(data)
