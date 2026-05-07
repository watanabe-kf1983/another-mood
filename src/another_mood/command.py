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
    BuildResult,
)
from another_mood.config import ProjectConfig
from another_mood.pipeline.stages import pipeline


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
    return pipeline(config, on_report=_lift(on_report)).run().to_result()


@contextmanager
def watch(
    config: ProjectConfig,
    on_report: Callable[[BuildResult], None],
) -> Iterator[Event]:
    """Start the pipeline in watch mode.

    Yields a shutdown :class:`Event`.  ``on_report`` fires after each rebuild
    with the iteration's BuildResult.  Cleans up watchers and the preview
    server on context exit.
    """
    with pipeline(config, on_report=_lift(on_report)).start_watching() as shutdown:
        yield shutdown


def _lift(
    on_report: Callable[[BuildResult], None] | None,
) -> Callable[[BuildReport], None] | None:
    """Adapt a BuildResult listener to the pipeline's BuildReport callback."""
    if on_report is None:
        return None
    return lambda report: on_report(report.to_result())
