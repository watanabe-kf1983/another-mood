"""Template engine — Jinja2 rendering behind a simple interface."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from reqs_builder.components.generator.section_processor import (
    SectionExtension,
    install as install_section_processor,
)


class TemplateEngine:
    def __init__(self, templates_dir: Path, out_dir: Path) -> None:
        self._env = Environment(
            extensions=[SectionExtension],
            keep_trailing_newline=True,
        )
        self._env.loader = FileSystemLoader(templates_dir)
        install_section_processor(self._env, out_dir)

    def render(self, template_name: str, data: dict[str, Any]) -> str:
        return self._env.get_template(f"{template_name}.md").render(data)
