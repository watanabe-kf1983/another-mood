"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Callable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import (
    ChainableUndefined,
    Environment,
    FileSystemLoader,
    TemplateSyntaxError,
)

from another_mood.components.generator.mood_view_processor import (
    MoodViewExtension,
    install as install_mood_view_processor,
)
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError

_BUILT_IN_TEMPLATES_DIR = resources.files("another_mood.resources") / "templates"


class TemplateEngine:
    def __init__(
        self,
        out_dir: Path,
        *,
        templates_dir: Path | None = None,
        filters: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._env = Environment(
            extensions=[MoodViewExtension],
            keep_trailing_newline=True,
            undefined=ChainableUndefined,
        )
        search_paths: list[str | Path] = [str(_BUILT_IN_TEMPLATES_DIR)]
        if templates_dir is not None:
            search_paths.append(templates_dir)
        self._env.loader = FileSystemLoader(search_paths)
        if filters is not None:
            for name, func in filters.items():
                self._env.filters[name] = func  # pyright: ignore[reportArgumentType]
        install_mood_view_processor(self._env, out_dir)

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
