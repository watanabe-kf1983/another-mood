"""Commands behind the CLI.

Each function performs the work of one user-visible command and returns its
result as a value.  No stderr / stdout writes from this module: the CLI
renders the value to the terminal.

Live progress / error feedback that does not fit into a return value (for
example, per-rebuild reports during watch) is delivered via callback
arguments (e.g. ``watch(..., on_report=...)``) — never via ``print``.
"""

import shutil
import tempfile
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from threading import Event

from another_mood.components.docs_catalog.catalog import (
    DocEntry,
    list_docs as _list_docs,
    read_doc as _read_doc,
)
from another_mood.components.manifest import Manifest, read_manifest
from another_mood.components.scaffold.blueprints import (
    DEFAULT_BLUEPRINT,
    Blueprint,
    ScaffoldResult,
    apply_blueprint as _apply_blueprint,
    available_blueprints as _available_blueprints,
)
from another_mood.components.shared.component.build_report import (
    BuildReport,
    ErrorEntry,
)
from another_mood.components.shared.user_error import UserError
from another_mood.components.shared.user_source.diagnostic import DiagnosticEntry
from another_mood.components.tap.tap import TAP_DOCUMENT_NAME
from another_mood.components.tap.tap import tap as tap_component
from another_mood.config import ProjectConfig
from another_mood.layout import SourceLayout, resolve_layout, verify_absent
from another_mood.pipeline.site import (
    HugoServerStartupError as WatchStartupError,
)
from another_mood.pipeline.stages import pipeline, tap_pipeline
from another_mood.pipeline.workspace import (
    ProcessorCommand,
    Workspace,
    make_processor_info,
)

# UserError is re-exported: commands raise its subclasses for pre-pipeline
# refusals, and the CLI catches that base.
__all__ = [
    "BuildResult",
    "ResultDiagnostic",
    "TapResult",
    "UserError",
    "WatchSession",
    "WatchStartupError",
    "apply_blueprint",
    "build",
    "init",
    "list_blueprints",
    "list_docs",
    "read_doc",
    "tap",
    "watch",
]

_logger = getLogger(__name__)


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


@dataclass(frozen=True, kw_only=True)
class _RunOutcome:
    """Outcome of a pipeline run, as exposed across the command-layer boundary.

    Slim view of a :class:`BuildReport` for CLI consumers.  Per-stage
    results and per-diagnostic snippets — both useful only for human debugging
    of the on-disk ``__build_report.json`` — are stripped here.  Each command
    adds what it hands back on success (:class:`BuildResult`,
    :class:`TapResult`).
    """

    errors: Sequence[ErrorEntry] = ()
    diagnostics: Sequence[ResultDiagnostic] = ()

    def has_errors(self) -> bool:
        return bool(self.errors)

    def has_internal_error(self) -> bool:
        return any(e.is_internal for e in self.errors)

    def has_warnings(self) -> bool:
        """True if any diagnostic was recorded with ``severity="warning"``."""
        return any(d.severity == "warning" for d in self.diagnostics)


@dataclass(frozen=True, kw_only=True)
class BuildResult(_RunOutcome):
    """``out_dir`` is the resolved directory where the run's published output
    landed (``.another-mood/<project_dir>/output/`` by default)."""

    out_dir: str


@dataclass(frozen=True, kw_only=True)
class TapResult(_RunOutcome):
    """``document`` is the tap document's JSON text, None when the run failed."""

    document: str | None


# -- Commands ----------------------------------------------------------------


def init(project_dir: Path) -> ScaffoldResult:
    """Initialize a new project from the default blueprint."""
    return apply_blueprint(DEFAULT_BLUEPRINT, project_dir)


def apply_blueprint(name: str, project_dir: Path) -> ScaffoldResult:
    """Copy the named blueprint into ``project_dir``.

    Raises :class:`ProjectExistsError` without writing anything if
    ``project_dir`` already holds a project.  The caller is responsible
    for validating ``name`` against :func:`list_blueprints`, and for
    handing in an absolute ``project_dir``.
    """
    _require_absolute("project_dir", project_dir)
    verify_absent(project_dir)
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
    config = config.resolved_for_build()
    out_dir = str(config.out_dir)
    # Manifest before layout: layout is also a format-generation contract, so
    # an unsupported sbdb_version must be reported before "source paths not
    # found".
    manifest = read_manifest(config.project_dir)
    layout = resolve_layout(config.project_dir)
    workspace = _session_workspace(config, layout, manifest, "build")
    result = _to_result(
        pipeline(workspace, on_report=_lift(on_report, out_dir)).run(), out_dir
    )
    _discard_workspace(workspace, keep_for_post_mortem=result.has_internal_error())
    return result


@contextmanager
def watch(
    config: ProjectConfig,
    on_report: Callable[[BuildResult], None],
) -> Generator[WatchSession]:
    """Start the pipeline in watch mode.

    Yields a :class:`WatchSession` once the live preview server is confirmed
    up.  Raises :class:`WatchStartupError` (before the ``with`` body runs) if
    the server fails to start — for example, when the port is already in use.

    ``on_report`` fires after each rebuild with the iteration's BuildResult.
    Cleans up watchers and the preview server on context exit.
    """
    config = config.resolved_for_watch()
    out_dir = str(config.out_dir or "")
    # Both read once at startup: the manifest is not watched, and rebuilds
    # do not re-check source existence.
    manifest = read_manifest(config.project_dir)
    layout = resolve_layout(config.project_dir)
    workspace = _session_workspace(config, layout, manifest, "watch")
    with pipeline(
        workspace, on_report=_lift(on_report, out_dir)
    ).start_watching() as shutdown:
        yield WatchSession(
            host=config.host,
            port=config.port,
            shutdown=shutdown,
        )


def tap(config: ProjectConfig) -> TapResult:
    """Run the pipeline through compose and return the composed namespace.

    Nothing is published: the document lives in the run's workspace and is
    handed back as ``document`` for the caller to print or pipe. Rendering
    stages never run, so template problems cannot fail a tap run; schema /
    contents / view errors can, in which case ``document`` is None and
    ``errors`` carries the report.
    """
    manifest = read_manifest(config.project_dir)
    layout = resolve_layout(config.project_dir)
    workspace = _session_workspace(config, layout, manifest, "tap")
    report = tap_pipeline(workspace).run()
    document_path = (
        workspace.component_output(tap_component).dir / "data" / TAP_DOCUMENT_NAME
    )
    document = (
        None if report.has_errors() else document_path.read_text(encoding="utf-8")
    )
    result = TapResult(
        document=document,
        errors=tuple(report.errors),
        diagnostics=tuple(ResultDiagnostic.from_entry(d) for d in report.diagnostics),
    )
    _discard_workspace(workspace, keep_for_post_mortem=result.has_internal_error())
    return result


# -- Helpers -----------------------------------------------------------------


def _require_absolute(name: str, path: Path) -> None:
    """Raise ValueError unless *path* is absolute."""
    if not path.is_absolute():
        raise ValueError(
            f"{name} must be an absolute path, got {str(path)!r}. Resolving "
            "one belongs to the CLI boundary that owns the caller's "
            "working directory."
        )


def _session_workspace(
    config: ProjectConfig,
    layout: SourceLayout,
    manifest: Manifest,
    command: ProcessorCommand,
) -> Workspace:
    """Build the run Workspace, defaulting its root to a fresh system-temp dir.

    An explicit ``tmp_dir`` (MOOD_TMP_DIR) is honored and left for the user to
    manage; otherwise a throwaway system-temp dir is created and marked
    ``temporary`` so the caller can clean it up.
    """
    # Stamped once per operation: a watch session's rebuilds must not move it.
    processor = make_processor_info(command)
    if config.tmp_dir is not None:
        return Workspace(config, config.tmp_dir, layout, manifest, processor)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="another-mood-"))
        return Workspace(config, tmp, layout, manifest, processor, temporary=True)


def _discard_workspace(workspace: Workspace, *, keep_for_post_mortem: bool) -> None:
    """Remove a throwaway workspace; a user-pinned one is left alone."""
    if not workspace.temporary:
        return
    if keep_for_post_mortem:
        _logger.error(
            "run failed internally; kept working dir for post-mortem: %s",
            workspace.root,
        )
    else:
        shutil.rmtree(workspace.root, ignore_errors=True)


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
