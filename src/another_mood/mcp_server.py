"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

import sys
from collections.abc import Sequence
from logging import INFO, basicConfig
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FileResource
from mcp.types import ResourceLink
from pydantic import AnyUrl

from another_mood import command
from another_mood.components.scaffold.blueprints import Blueprint, ScaffoldResult
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.config import ProjectConfig

mcp = FastMCP("another-mood")

# Bundled docs are exposed via Resources (canonical) and via list_docs /
# read_doc Tools below (mirror, for clients that don't surface Resources).
for _entry in command.list_docs():
    mcp.add_resource(
        FileResource(
            uri=AnyUrl(_entry.uri),
            name=_entry.name,
            description=_entry.description,
            mime_type=_entry.mime_type,
            path=_entry.path,
        )
    )


@mcp.tool()
def list_docs() -> Sequence[ResourceLink]:
    """List bundled Another Mood documentation as MCP resource links.

    The catalog covers Another Mood's CLI commands, schema language, query
    syntax, template syntax, and built-in meta-schemas.  Pass any returned
    `uri` to `read_doc()` to fetch its contents.
    """
    return [
        ResourceLink(
            type="resource_link",
            uri=AnyUrl(e.uri),
            name=e.name,
            description=e.description,
            mimeType=e.mime_type,
        )
        for e in command.list_docs()
    ]


@mcp.tool()
def read_doc(uri: str) -> str:
    """Read a bundled Another Mood document by its `docs://` URI.

    `uri` must be one of the values returned by `list_docs()` (e.g.
    `docs://reference/cli.md`).  Returns the raw file contents as text.
    """
    return command.read_doc(uri)


@mcp.tool()
def build(project_dir: str) -> BuildReport:
    """Run the Another Mood build pipeline once over `project_dir` and return
    the build report. Equivalent to `mood build <project_dir>`.

    Use this in an edit-build-inspect feedback loop after editing source
    files. The pipeline reads `definition/` and `contents/` under
    `project_dir` and emits Markdown + rendered HTML to
    `.another-mood/<project_dir>/output/`.

    Raises `ConfigValidationError` if `project_dir` or required source paths
    are missing. Pipeline-internal failures do not raise — they appear as
    entries in the returned report's `errors` and `diagnostics` fields.

    For DSL syntax, see `read_doc()` (catalog via `list_docs()`).
    """
    config = ProjectConfig(project_dir=Path(project_dir))
    config.verify()
    return command.build(config)


@mcp.tool()
def init(project_dir: str) -> ScaffoldResult:
    """Scaffold a new Another Mood project at `project_dir` from the default
    blueprint (a minimal starter).

    The directory is created if it does not exist.  Existing files are never
    overwritten; their paths are returned in `skipped`.  Run `build` next to
    produce output from the scaffolded sources.

    To choose a different blueprint, use `list_blueprints` + `apply_blueprint`
    instead; `init` is a shortcut for `apply_blueprint("starter", ...)`.
    """
    return command.init(Path(project_dir))


@mcp.tool()
def list_blueprints() -> Sequence[Blueprint]:
    """List bundled blueprints (sample projects) as `{name, description}` records.

    Each blueprint is a self-contained Another Mood project that demonstrates
    a particular shape of source.  Pass any returned `name` to `apply_blueprint`
    to copy that blueprint into a target directory.
    """
    return command.list_blueprints()


@mcp.tool()
def apply_blueprint(name: str, project_dir: str) -> ScaffoldResult:
    """Copy the named blueprint into `project_dir`.

    `name` must be one of the names returned by `list_blueprints()`; an unknown
    name raises `ValueError`.  The directory is created if it does not exist.
    Existing files are never overwritten; their paths are returned in
    `skipped`.  Run `build` next to produce output from the copied sources.
    """
    available = [b.name for b in command.list_blueprints()]
    if name not in available:
        raise ValueError(
            f"unknown blueprint: {name!r} (available: {', '.join(available)})"
        )
    return command.apply_blueprint(name, Path(project_dir))


def main() -> None:
    basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
    mcp.run()
