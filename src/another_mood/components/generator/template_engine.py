"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
    PROCESSOR_KEY,
    MoodViewExtension,
    MoodViewProcessorImpl,
)
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)


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
        templates_dir: Path,
        filters: Mapping[str, Callable[..., Any]],
    ) -> None:
        self._out_dir = out_dir
        self._env = make_environment(MD)
        self._env.loader = FileSystemLoader(str(templates_dir))
        for name, func in filters.items():
            self._env.filters[name] = func  # pyright: ignore[reportArgumentType]
        self._source_stack: list[Path] = []
        # The mood_view extension dispatches via env.globals[PROCESSOR_KEY].
        self._env.globals[PROCESSOR_KEY] = MoodViewProcessorImpl(engine=self)  # pyright: ignore[reportArgumentType]

    def current_source(self) -> Path | None:
        """out_dir-relative path of the page currently being rendered, or
        None outside any ``render_to_file`` call."""
        return self._source_stack[-1] if self._source_stack else None

    def render(self, template_name: str, data: Mapping[str, object]) -> str:
        """Render and return the result. Inherits the source stack — does
        not push, so this is for fragments inside an enclosing render_to_file."""
        return self._render(template_name, data)

    def render_to_file(
        self,
        template_name: str,
        data: Mapping[str, object],
        out_path: Path,
    ) -> None:
        """Render and write to ``out_dir / out_path``. The out_dir-relative
        ``out_path`` is pushed onto the source stack for the duration of
        the render. Nothing is written if rendering fails."""
        self._source_stack.append(out_path)
        try:
            rendered = self._render(template_name, data)
        finally:
            self._source_stack.pop()
        out_file = self._out_dir / out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")

    def _render(self, template_name: str, data: Mapping[str, object]) -> str:
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
