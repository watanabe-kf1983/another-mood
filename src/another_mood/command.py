"""Commands shared between CLI and MCP server.

Each function performs the work of one user-visible command and returns its
result as a value.  No stderr / stdout writes from this module: the CLI
renders the value to the terminal; MCP tools return it to the agent.

Live progress / error feedback that does not fit into a return value (for
example, per-rebuild reports during watch) is delivered via callback
arguments (e.g. ``watch(..., on_report=...)``) — never via ``print``.
"""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from another_mood.components.docs_catalog.catalog import (
    DocEntry,
    list_docs as _list_docs,
    read_doc as _read_doc,
)
from another_mood.components.scaffold.blueprints import (
    DEFAULT_BLUEPRINT,
    Blueprint,
    ScaffoldResult,
    apply_blueprint as _apply_blueprint,
    available_blueprints as _available_blueprints,
)
from another_mood.components.shared.component.build_report import (
    BuildReport,
    DiagnosticEntry,
    ErrorEntry,
)
from another_mood.config import ProjectConfig
from another_mood.pipeline.render import (
    HugoServerStartupError as WatchStartupError,
)
from another_mood.pipeline.stages import pipeline

__all__ = [
    "BuildResult",
    "ResultDiagnostic",
    "WatchSession",
    "WatchStartupError",
    "apply_blueprint",
    "build",
    "init",
    "list_blueprints",
    "list_docs",
    "read_doc",
    "watch",
]


# -- Boundary types ----------------------------------------------------------


@dataclass(frozen=True)
class ResultDiagnostic:
    """Slim diagnostic for the agent boundary: DiagnosticEntry sans snippet.

    The snippet is a code-frame intended for human readers (`__build_failure`
    Markdown page).  Agents read source files directly and have no use for it.
    """

    file: str
    line: int | None
    column: int | None
    message: str
    severity: str = "error"
    source: str = ""

    @classmethod
    def from_entry(cls, e: DiagnosticEntry) -> "ResultDiagnostic":
        return cls(
            file=e.file,
            line=e.line,
            column=e.column,
            message=e.message,
            severity=e.severity,
            source=e.source,
        )


@dataclass(frozen=True)
class WatchSession:
    """Live preview session details, yielded by :func:`watch`.

    Carries the raw bind ``host`` / ``port`` the dev server is listening on;
    URL formatting (including LAN-IP substitution for wildcard binds) is left
    to the caller, since that's a presentation choice that varies per consumer.
    ``shutdown`` fires when the dev server exits unexpectedly during the
    session — block on it to keep the session alive.
    """

    host: str
    port: int
    shutdown: Event


@dataclass(frozen=True)
class BuildResult:
    """Outcome of a build, as exposed across the command-layer boundary.

    Slim view of a :class:`BuildReport` for CLI / MCP consumers.  Per-stage
    results and per-diagnostic snippets — both useful only for human debugging
    of the on-disk ``__build_report.yaml`` — are stripped here.

    ``out_dir`` is the resolved directory where rendered output landed
    (typically ``.another-mood/<project_dir>/output/``).
    """

    out_dir: str
    errors: Sequence[ErrorEntry] = ()
    diagnostics: Sequence[ResultDiagnostic] = ()

    def has_errors(self) -> bool:
        return bool(self.errors)


# -- Commands ----------------------------------------------------------------


def init(project_dir: Path) -> ScaffoldResult:
    """Initialize a new project from the default blueprint."""
    return _apply_blueprint(DEFAULT_BLUEPRINT, project_dir)


def apply_blueprint(name: str, project_dir: Path) -> ScaffoldResult:
    """Copy the named blueprint into ``project_dir``.

    The caller is responsible for validating ``name`` against
    :func:`list_blueprints`.
    """
    return _apply_blueprint(name, project_dir)


def list_blueprints() -> Sequence[Blueprint]:
    """Return the bundled blueprint manifest in declared order."""
    return _available_blueprints()


def list_docs() -> Sequence[DocEntry]:
    """Return the bundled documentation catalog."""
    return _list_docs()


def read_doc(uri: str) -> str:
    """Read a bundled doc by its ``docs://`` URI.

    Raises ``ValueError`` if ``uri`` is not in the catalog (catalog-external
    paths are rejected).
    """
    return _read_doc(uri)


def build(
    config: ProjectConfig,
    on_report: Callable[[BuildResult], None] | None = None,
) -> BuildResult:
    """Run the build pipeline once and return the resulting BuildResult.

    ``on_report`` fires once during the run, just before the result is
    returned.  Provided for symmetry with :func:`watch`; one-shot callers
    that only need the final value can omit it and use the return value.
    """
    out_dir = str(config.out_dir)
    report = pipeline(config, on_report=_lift(on_report, out_dir)).run()
    return _to_result(report, out_dir)


@contextmanager
def watch(
    config: ProjectConfig,
    on_report: Callable[[BuildResult], None],
) -> Iterator[WatchSession]:
    """Start the pipeline in watch mode.

    Yields a :class:`WatchSession` once the live preview server is confirmed
    up.  Raises :class:`WatchStartupError` (before the ``with`` body runs) if
    the server fails to start — for example, when the port is already in use.

    ``on_report`` fires after each rebuild with the iteration's BuildResult.
    Cleans up watchers and the preview server on context exit.
    """
    out_dir = str(config.out_dir)
    with pipeline(
        config, on_report=_lift(on_report, out_dir)
    ).start_watching() as shutdown:
        yield WatchSession(
            host=config.host,
            port=config.port,
            shutdown=shutdown,
        )


# -- Helpers -----------------------------------------------------------------


def _to_result(report: BuildReport, out_dir: str) -> BuildResult:
    """Project a pipeline-internal BuildReport to a BuildResult."""
    return BuildResult(
        out_dir=out_dir,
        errors=tuple(report.errors),
        diagnostics=tuple(ResultDiagnostic.from_entry(d) for d in report.diagnostics),
    )


def _lift(
    on_report: Callable[[BuildResult], None] | None,
    out_dir: str,
) -> Callable[[BuildReport], None] | None:
    """Adapt a BuildResult listener to the pipeline's BuildReport callback."""
    if on_report is None:
        return None
    return lambda report: on_report(_to_result(report, out_dir))
