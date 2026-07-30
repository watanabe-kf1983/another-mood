"""Template engine — MiniJinja rendering behind a simple interface."""

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Concatenate, cast

from minijinja import Environment, TemplateError, load_from_path

from another_mood.components.generator.render_processor import RenderProcessorImpl
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.generator.template_safe import (
    TemplateSafe,
    ensure_template_safe,
)
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
    # Block whitespace control, owned by the format because whitespace
    # significance is format-dependent.  lstrip_blocks drops the indentation
    # before a line's `{% %}` tag; trim_blocks drops the newline after it —
    # together they let a control tag sit on its own indented line and emit
    # nothing, so templates can show their structure without leaking spaces or
    # blank lines.  Defaults match the engine's own (off); a format opts in.
    trim_blocks: bool = False
    lstrip_blocks: bool = False
    # A format's final pass over a rendered output, given the subject. Runs
    # once per render via the engine's single render funnel — e.g. md stamps
    # the subject node's anchor at the top. Defaults to identity; a format
    # opts in.
    post_process: Callable[[str, object], str] = _identity_post_process


def make_environment(output_format: OutputFormat) -> Environment:
    # Per-format escaping is implemented via the finalizer hook; Markup values
    # are passed through.
    def _finalize(value: object) -> object:
        if value is None:
            return ""
        if hasattr(value, "__html__"):
            return str(value)
        return output_format.escape(str(value))

    # No filters / globals are registered here: the caller assembles them (the
    # format's own helpers plus its config / node-map-bound ones) and passes
    # them to TemplateEngine, which registers them on this env.
    return Environment(
        keep_trailing_newline=True,
        trim_blocks=output_format.trim_blocks,
        lstrip_blocks=output_format.lstrip_blocks,
        # Chainable, so a missing step part-way through `{{ a.b.c }}` keeps
        # resolving instead of raising; what it yields arrives as `None`.
        undefined_behavior="chainable",
        finalizer=_finalize,
        # Off unconditionally: escaping is `_finalize`'s, and auto-escape keys
        # off the template's extension — an `.html`-named one would otherwise be
        # HTML-escaped on top.
        auto_escape_callback=lambda name: False,
        # Explicit though it is the default: the meta templates call Python's
        # `.startswith()` / `.endswith()`, which only exist under pycompat.
        pycompat=True,
    )


class EnvironmentPool:
    """Lends Environments out, at most one live render to each — minijinja
    deadlocks when a render re-enters the Environment it is already running on,
    which the ``render`` filter otherwise does.  Not thread-safe: an engine
    renders on one thread.
    """

    def __init__(self, new_environment: Callable[[], Environment]) -> None:
        self._new_environment = new_environment
        self._idle: list[Environment] = []

    @contextmanager
    def acquire(self) -> Generator[Environment]:
        # Most recently released first, so a given nesting depth keeps landing
        # on the same Environment and its parse cache stays warm.
        env = self._idle.pop() if self._idle else self._new_environment()
        try:
            yield env
        finally:
            self._idle.append(env)


def as_template_helper[**P, T](
    processor: Callable[Concatenate[str, P], T],
) -> Callable[Concatenate[object, P], T | None]:
    """Wrap a text processor for registration, giving it the subject a template
    can actually hand over.

    This is the render boundary's intake half, to ``_finalize``'s output half: a
    format supplies plain text processing, and what reaching one from a template
    involves is the boundary's business.  Templates pipe in arbitrary values, so
    the subject is coerced to ``str``.  An absent subject is not text at all: it
    skips the processor and passes through as ``None``, leaving ``_finalize`` the
    only place that renders absence — so no processor stringifies it into
    ``"None"``.

    A helper whose subject is a node rather than text needs neither and is
    registered as it is.
    """

    @wraps(processor)
    def helper(value: object, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if value is None:
            return None
        return processor(str(value), *args, **kwargs)

    return helper


def _bind(subject: object) -> Mapping[str, TemplateSafe]:
    """Build a template's render context: bind the subject as ``this``.

    A Mapping subject additionally spreads its keys as top-level names, so
    bare ``{{ field }}`` access works without a ``this.`` prefix.  ``this``
    is reserved: a subject key of that name is shadowed by the binding.

    Each binding is marshaled through the render boundary, raising if it is not
    template-safe.
    """
    if isinstance(subject, Mapping):
        fields = cast(Mapping[str, object], subject)
        context: Mapping[str, object] = {**fields, "this": fields}
    else:
        context = {"this": subject}
    return {name: ensure_template_safe(value) for name, value in context.items()}


class PageCollisionError(UserError):
    """Two distinct pages resolved to the same output file.

    Raised by the engine when a rendered page would overwrite
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
            f"duplicate `render` call."
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
        filters: Mapping[str, Callable[..., TemplateSafe]],
        globals: Mapping[str, Callable[..., TemplateSafe]] = {},
        paging: PagingPolicy = PagingPolicy(),
    ) -> None:
        self._out_dir = out_dir
        self._templates_dir = templates_dir
        self._paths = PathRegistry()
        self._output_format = output_format
        processor = RenderProcessorImpl(engine=self, paging=paging)

        def new_environment() -> Environment:
            env = make_environment(output_format)
            env.loader = load_from_path(templates_dir)
            for name, func in filters.items():
                env.add_filter(name, func)
            for name, func in globals.items():
                env.add_global(name, func)
            # Registered after the caller's filters: engine-owned, not overridable.
            env.add_filter("render", processor.render_filter)
            return env

        self._envs = EnvironmentPool(new_environment)

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
            with self._envs.acquire() as env:
                rendered = env.render_template(template_name, **_bind(subject))
        except TemplateError as exc:
            # Catches syntax and runtime template errors alike.  A Python
            # exception from one of our own filters is not wrapped in one of
            # these, so it still propagates on its own terms.
            raise FileValidationError(
                [
                    Diagnostic(
                        # `exc.name` is the loader key, not a path — rejoin it or
                        # the diagnostic cannot read the file for its snippet.
                        file=self._templates_dir / (exc.name or template_name),
                        line=exc.line,
                        column=None,
                        # `message` would re-state the location held above.
                        message=exc.detail or exc.message,
                        source="minijinja",
                    )
                ]
            ) from exc
        return self._output_format.post_process(rendered, subject)
