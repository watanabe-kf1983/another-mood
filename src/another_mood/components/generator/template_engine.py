"""Template engine — Jinja2 rendering behind a simple interface."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.shared.user_error import UserError
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)


def _identity_post_process(rendered: str, subject: object) -> str:
    return rendered


@dataclass(frozen=True)
class OutputFormat:
    """A format's render policy — all the engine needs to know about it.  The
    template helpers (filters / globals) are not policy: the caller assembles
    and injects them via ``TemplateEngine``'s ``filters`` / ``globals``."""

    name: str
    escape: Callable[[str], str]
    # Jinja2 block whitespace control, owned by the format because whitespace
    # significance is format-dependent.  lstrip_blocks drops the indentation
    # before a line's `{% %}` tag; trim_blocks drops the newline after it —
    # together they let a control tag sit on its own indented line and emit
    # nothing, so templates can show their structure without leaking spaces or
    # blank lines.  Defaults match Jinja2's own (off); a format opts in.
    trim_blocks: bool = False
    lstrip_blocks: bool = False
    # A format's final pass over a rendered output, given the subject. Runs
    # once per render via the engine's single render funnel — e.g. md stamps
    # the subject node's anchor at the top. Defaults to identity; a format
    # opts in.
    post_process: Callable[[str, object], str] = _identity_post_process


def make_environment(output_format: OutputFormat) -> Environment:
    # Jinja2's autoescape is hard-coded to HTML, so per-format escaping
    # is implemented via a finalize hook; Markup values are passed through.
    def _finalize(value: object) -> object:
        if value is None or isinstance(value, Undefined):
            return ""
        if hasattr(value, "__html__"):
            return str(value)
        return output_format.escape(str(value))

    # No filters / globals are registered here: the caller assembles them (the
    # format's own helpers plus its config / node-map-bound ones) and passes
    # them to TemplateEngine, which registers them on this env.
    return Environment(
        extensions=[MoodViewExtension],
        keep_trailing_newline=True,
        trim_blocks=output_format.trim_blocks,
        lstrip_blocks=output_format.lstrip_blocks,
        undefined=ChainableUndefined,
        finalize=_finalize,
    )


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


class PageCollisionError(UserError):
    """Two distinct pages resolved to the same output file.

    Raised by the engine when a ``{% mood_view %}`` page would overwrite
    one already written this build under a different subject or template —
    distinct pages must not share an output path, or one silently clobbers
    the other.  The guidance is the exception's ``args[0]`` so it surfaces
    verbatim in the build report and CLI log (the ``UserError`` contract).
    """

    def __init__(self, out_path: Path, prev_template: str, new_template: str) -> None:
        origin = (
            f"template {prev_template!r} rendered it twice"
            if prev_template == new_template
            else f"templates {prev_template!r} and {new_template!r}"
        )
        super().__init__(
            f"Two pages resolved to the same output file {out_path} "
            f"({origin}). Each page needs a unique path — this usually means "
            f"two records share an id, or one record is rendered as a page "
            f"more than once. Give the records distinct ids, or drop the "
            f"duplicate {{% mood_view %}} call."
        )


@dataclass(frozen=True)
class _Claim:
    """Who holds an out_path: the rendered subject and its template."""

    subject: object
    template: str


class PathRegistry:
    """Tracks which page holds each output path within one render tree.

    Keeps one page from silently clobbering another: each path is
    claimable once, an identical re-claim is a no-op, and a conflicting
    claim raises.  Owns no rendering — just the bookkeeping — so it is
    unit-testable on its own.
    """

    def __init__(self) -> None:
        self._claimed: dict[Path, _Claim] = {}

    def claim(self, out_path: Path, subject: object, template_name: str) -> bool:
        """Reserve ``out_path`` for this page; return whether to write it.

        First claim records the ``(subject, template_name)`` and returns
        ``True``.  A repeat by the same subject (identity) and template is
        an idempotent no-op (``False``).  Any other repeat raises
        :class:`PageCollisionError` rather than let one page clobber
        another.
        """
        if prior := self._claimed.get(out_path):
            if prior.subject is subject and prior.template == template_name:
                return False
            else:
                raise PageCollisionError(out_path, prior.template, template_name)
        else:
            self._claimed[out_path] = _Claim(subject, template_name)
            return True


class TemplateEngine:
    def __init__(
        self,
        out_dir: Path,
        *,
        templates_dir: Path,
        output_format: OutputFormat,
        filters: Mapping[str, Callable[..., Any]],
        globals: Mapping[str, Callable[..., Any]] = {},
        paging: PagingPolicy = PagingPolicy(),
    ) -> None:
        self._out_dir = out_dir
        self._paths = PathRegistry()
        self._output_format = output_format
        self._env = make_environment(output_format)
        self._env.loader = FileSystemLoader(str(templates_dir))
        for name, func in filters.items():
            self._env.filters[name] = func  # pyright: ignore[reportArgumentType]
        for name, func in globals.items():
            self._env.globals[name] = func  # pyright: ignore[reportArgumentType]
        # The mood_view extension dispatches via env.globals[PROCESSOR_KEY].
        self._env.globals[PROCESSOR_KEY] = MoodViewProcessorImpl(  # pyright: ignore[reportArgumentType]
            engine=self, paging=paging
        )

    def render(self, template_name: str, subject: object) -> str:
        return self._render(template_name, subject)

    def render_to_file(
        self,
        template_name: str,
        subject: object,
        out_path: Path,
    ) -> None:
        """Render ``subject`` through ``template_name`` and write it to
        ``out_dir / out_path``.  Nothing is written if rendering fails.
        """
        if not self._paths.claim(out_path, subject, template_name):
            return
        rendered = self._render(template_name, subject)
        out_file = self._out_dir / out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")

    def _render(self, template_name: str, subject: object) -> str:
        try:
            rendered = self._env.get_template(template_name).render(_bind(subject))
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
        return self._output_format.post_process(rendered, subject)
