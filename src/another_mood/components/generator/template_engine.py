"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

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


def _bind(subject: object) -> Mapping[str, object]:
    """Build a template's render context: bind the subject as ``this``.

    A Mapping subject additionally spreads its keys as top-level names, so
    bare ``{{ field }}`` access works without a ``this.`` prefix.  ``this``
    is reserved: a subject key of that name is shadowed by the binding.
    """
    if isinstance(subject, Mapping):
        fields = cast(Mapping[str, object], subject)
        return {**fields, "this": fields}
    else:
        return {"this": subject}


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
        # The mood_view extension dispatches via env.globals[PROCESSOR_KEY].
        self._env.globals[PROCESSOR_KEY] = MoodViewProcessorImpl(engine=self)  # pyright: ignore[reportArgumentType]

    def render(self, template_name: str, subject: object) -> str:
        return self._render(template_name, subject)

    def render_to_file(
        self,
        template_name: str,
        subject: object,
        out_path: Path,
    ) -> None:
        """Render and write to ``out_dir / out_path``. Nothing is written
        if rendering fails."""
        rendered = self._render(template_name, subject)
        out_file = self._out_dir / out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")

    def _render(self, template_name: str, subject: object) -> str:
        try:
            return self._env.get_template(template_name).render(_bind(subject))
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
