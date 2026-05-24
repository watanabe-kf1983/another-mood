"""Template engine — Jinja2 rendering behind a simple interface."""

import re
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
    """Descriptor pairing an output format's escape rule with its filters.

    `escape` is applied to bare strings by ``make_environment``'s finalize
    hook. `filters` are registered on the produced Environment; any filter
    that returns a ``Markup`` instance is treated as having completed its
    own escaping and bypasses the finalize escape (see output-format-spec).
    """

    name: str
    escape: Callable[[str], str]
    filters: Mapping[str, Callable[..., Any]] = field(
        default_factory=lambda: {},
    )


# CommonMark allows any ASCII punctuation to be backslash-escaped, and the
# rendered output matches the unescaped character — so blanket-escaping every
# ASCII punctuation byte is safe and prevents accidental syntax (`#`/`-`/`*`
# at line start, `|` in tables, `_`/`*` emphasis, `<` HTML, `` ` `` code, etc.).
_MD_ESCAPE_PATTERN = re.compile(r"([!-/:-@\[-`{-~])")


def md_escape(text: str) -> str:
    """Backslash-escape every ASCII punctuation character in ``text``.

    Intended as the ``escape`` of the ``md`` ``OutputFormat`` — applied to bare
    strings by ``make_environment``'s finalize hook. Code-literal contexts
    (inline code spans, fenced code blocks, Mermaid fences) must bypass this
    via ``| safe`` at the template call site, since CommonMark does not
    process backslash escapes inside those contexts.
    """
    return _MD_ESCAPE_PATTERN.sub(r"\\\1", text)


MD = OutputFormat(name="md", escape=md_escape)


def make_environment(output_format: OutputFormat) -> Environment:
    """Build a Jinja2 Environment wired for `output_format`.

    `autoescape` stays off (Jinja2's autoescape is hard-coded to HTML);
    instead a `finalize` hook applies ``output_format.escape`` to bare
    strings while passing ``Markup`` through untouched. ``None`` and
    ``Undefined`` collapse to the empty string.
    """

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
    for name, func in output_format.filters.items():
        env.filters[name] = func  # pyright: ignore[reportArgumentType]
    return env


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
