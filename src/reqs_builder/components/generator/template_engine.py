"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

from reqs_builder.components.generator.section_processor import (
    SectionExtension,
    install as install_section_processor,
)
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_BUILT_IN_TEMPLATES_DIR = resources.files("reqs_builder.resources") / "templates"


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

    def render(self, template_name: str, data: Mapping[str, object]) -> str:
        try:
            return self._env.get_template(f"{template_name}.md").render(data)
        except TemplateSyntaxError as exc:
            raise FileValidationError(
                [
                    Diagnostic(
                        file=Path(exc.filename or template_name),
                        line=exc.lineno,
                        column=None,
                        message=str(exc.message),
                        source="jinja2",
                    )
                ]
            ) from exc
