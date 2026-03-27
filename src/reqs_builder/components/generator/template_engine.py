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
_ERRORS_TEMPLATE = "__errors.md"


class TemplateEngine:
    def __init__(self, out_dir: Path, *, templates_dir: Path | None = None) -> None:
        self._env = Environment(
            extensions=[SectionExtension],
            keep_trailing_newline=True,
        )
        search_paths: list[str | Path] = [str(_BUILT_IN_TEMPLATES_DIR)]
        if templates_dir is not None:
            search_paths.append(templates_dir)
        self._env.loader = FileSystemLoader(search_paths)
        install_section_processor(self._env, out_dir)

    def render(self, data: dict[str, Any]) -> str:
        template = _ERRORS_TEMPLATE if "__errors" in data else _ROOT_TEMPLATE
        return self._env.get_template(template).render(data)
