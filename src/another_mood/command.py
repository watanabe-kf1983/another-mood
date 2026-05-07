"""Commands shared between CLI and MCP server.

Each function performs the work of one user-visible command and returns its
result as a value.  No stderr / stdout writes from this module: the CLI
renders the value to the terminal; MCP tools return it to the agent.

Live progress / error feedback that does not fit into a return value (for
example, per-rebuild reports during watch) is delivered via callback
arguments (e.g. ``watch(..., on_report=...)``) — never via ``print``.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
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
    ScaffoldResult,
    apply_blueprint as _apply_blueprint,
    available_blueprints as _available_blueprints,
)
from another_mood.components.shared.component.build_report import BuildReport
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


def list_blueprints() -> Mapping[str, str]:
    """Return the bundled blueprint manifest as ``name -> description``."""
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
    on_report: Callable[[BuildReport], None] | None = None,
) -> BuildReport:
    """Run the build pipeline once and return the resulting BuildReport.

    ``on_report`` fires once during the run, just before the report is
    returned.  Provided for symmetry with :func:`watch`; one-shot callers
    that only need the final value can omit it and use the return value.
    """
    return pipeline(config, on_report=on_report).run()


@contextmanager
def watch(
    config: ProjectConfig,
    on_report: Callable[[BuildReport], None],
) -> Iterator[Event]:
    """Start the pipeline in watch mode.

    Yields a shutdown :class:`Event`.  ``on_report`` fires after each rebuild
    with the iteration's BuildReport.  Cleans up watchers and the preview
    server on context exit.
    """
    with pipeline(config, on_report=on_report).start_watching() as shutdown:
        yield shutdown
