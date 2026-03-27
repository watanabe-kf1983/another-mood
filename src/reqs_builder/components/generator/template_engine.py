"""Template engine — Jinja2 rendering behind a simple interface."""

from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from reqs_builder.components.generator.section_processor import (
    SectionExtension,
    install as install_section_processor,
)

_BUILT_IN_TEMPLATES_DIR = resources.files("reqs_builder.resources") / "templates"

_ROOT_TEMPLATE = "__root.md"


class TemplateEngine:
    def __init__(self, templates_dir: Path, out_dir: Path) -> None:
        self._env = Environment(
            extensions=[SectionExtension],
            keep_trailing_newline=True,
        )
        self._env.loader = FileSystemLoader(
            [str(_BUILT_IN_TEMPLATES_DIR), templates_dir]
        )
        install_section_processor(self._env, out_dir)

    def render(self, data: dict[str, Any]) -> str:
        return self._env.get_template(_ROOT_TEMPLATE).render(data)
