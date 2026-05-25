"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import (
    ChainableUndefined,
    Environment,
    FileSystemLoader,
    TemplateSyntaxError,
    Undefined,
)

from another_mood.components.generator.mood_view_processor import (
    MoodViewExtension,
    install as install_mood_view_processor,
)
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError

_BUILT_IN_TEMPLATES_DIR = resources.files("another_mood.resources") / "templates"


@dataclass(frozen=True)
class OutputFormat:
    name: str
    escape: Callable[[str], str]
    globals: Mapping[str, Callable[..., Any]] = field(
        default_factory=lambda: {},
    )
    filters: Mapping[str, Callable[..., Any]] = field(
        default_factory=lambda: {},
    )


def make_environment(output_format: OutputFormat) -> Environment:
    # Jinja2's autoescape is hard-coded to HTML, so per-format escaping
    # is implemented via a finalize hook; Markup values are passed through.
    def _finalize(value: object) -> object:
        if value is None or isinstance(value, Undefined):
            return ""
        if hasattr(value, "__html__"):
            return str(value)
        return output_format.escape(str(value))

    env = Environment(
        extensions=[MoodViewExtension],
        keep_trailing_newline=True,
        undefined=ChainableUndefined,
        finalize=_finalize,
    )
    for name, func in output_format.globals.items():
        env.globals[name] = func  # pyright: ignore[reportArgumentType]
    for name, func in output_format.filters.items():
        env.filters[name] = func  # pyright: ignore[reportArgumentType]
    return env


# Imported after OutputFormat is defined to break a circular import.
from another_mood.components.generator.output_formats.md import MD  # noqa: E402


class TemplateEngine:
    def __init__(
        self,
        out_dir: Path,
        *,
        templates_dir: Path | None = None,
        filters: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._env = make_environment(MD)
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
            return self._env.get_template(template_name).render(data)
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
