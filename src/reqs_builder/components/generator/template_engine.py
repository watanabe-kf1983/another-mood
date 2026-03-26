"""Template engine — Jinja2 rendering behind a simple interface."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from reqs_builder.components.generator.section_processor import (
    SectionExtension,
    install as install_section_processor,
)


def render(
    template_name: str,
    templates_dir: Path,
    data: dict[str, Any],
    out_dir: Path,
) -> str:
    """Render a template with data and write section pages to out_dir."""
    env = Environment(
        extensions=[SectionExtension],
        keep_trailing_newline=True,
    )
    env.loader = FileSystemLoader(templates_dir)
    install_section_processor(env, out_dir)

    return env.get_template(f"{template_name}.md").render(data)
