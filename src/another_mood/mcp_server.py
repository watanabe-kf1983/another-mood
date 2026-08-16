"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

import sys
from collections.abc import Sequence
from logging import INFO, basicConfig
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import FileResource
from mcp.types import ResourceLink

from another_mood import command
from another_mood.command import BuildResult
from another_mood.components.scaffold.blueprints import Blueprint, ScaffoldResult
from another_mood.components.shared.tool_version import tool_version
from another_mood.config import ProjectConfig

_INSTRUCTIONS = """\
Another Mood manages a source-based database: a set of YAML and Markdown
files that, when built, generates a synchronized set of Markdown and HTML
documents. Editing a source file in one place keeps every page derived
from it consistent.

The source files live under `<project_dir>/` and fall into four kinds:

- `definition/schema.yaml` declares data types
- `contents/` holds data (YAML records or Markdown prose)
- `definition/views/` (optional) declares views that reshape data
- `definition/templates/` describes output pages

Workflow:

- Start a project: call `init(project_dir)` for the default starter, or
  `list_blueprints` + `apply_blueprint(name, project_dir)` to pick a
  specific blueprint.
- After editing sources: call `build(project_dir)` and inspect the result.
  The `output/__entity_defs/`, `__view_defs/`, and `__data/`
  subdirectories under the build output are auto-generated diagnostic
  views — read them mid-edit to verify how schema, data, and views
  resolved.
- Before editing schema, view, or template files, consult the reference:
  call `list_docs()` for the catalog, then `read_doc(uri)` with a
  `docs://` URI from the listing.
- To query the project's data rather than its rendered pages, call `tap`.

Another Mood also provides live preview, but not as an MCP tool. Ask the
user to run `mood watch <project_dir>` in a separate terminal.
"""

mcp = MCPServer("another-mood", instructions=_INSTRUCTIONS, version=tool_version())

# Bundled docs are exposed via Resources (canonical) and via list_docs /
# read_doc Tools below (mirror, for clients that don't surface Resources).
for _entry in command.list_docs():
    mcp.add_resource(
        FileResource(
            uri=_entry.uri,
            name=_entry.name,
            description=_entry.description,
            mime_type=_entry.mime_type,
            path=_entry.path,
        )
    )


@mcp.tool()
def list_docs() -> Sequence[ResourceLink]:
    """List bundled documentation as MCP resource links.
    Equivalent to `mood docs list`.
    """
    return [
        ResourceLink(
            type="resource_link",
            uri=e.uri,
            name=e.name,
            description=e.description,
            mime_type=e.mime_type,
        )
        for e in command.list_docs()
    ]


@mcp.tool()
def read_doc(uri: str) -> str:
    """Read a bundled document by its `docs://` URI.
    Equivalent to `mood docs read <uri>`.

    `uri` must be one of the values returned by `list_docs()` (e.g.
    `docs://reference/cli.md`).
    """
    return command.read_doc(uri)


@mcp.tool()
def build(
    project_dir: str,
    out_dir: str | None = None,
    site_dir: str | None = None,
    vars: dict[str, str] | None = None,
) -> BuildResult:
    """Run a one-shot build of `project_dir`, generating Markdown and HTML
    and returning the result. Equivalent to `mood build <project_dir>`.

    Paths must be absolute. `out_dir` and `site_dir` are optional; leave them
    unset to use the defaults under `<project_dir>/.another-mood/`.

    `vars` carries values of your own for templates to read back through
    `build_info("vars.<name>")`; every entry is listed on the colophon page.
    """
    overrides = _project_overrides(project_dir)
    if out_dir is not None:
        overrides["out_dir"] = _absolute_arg("out_dir", out_dir)
    if site_dir is not None:
        overrides["site_dir"] = _absolute_arg("site_dir", site_dir)
    config = ProjectConfig(**overrides)  # type: ignore[arg-type]
    config.verify()
    return command.build(config.with_injected_vars(vars or {}))


@mcp.tool()
def tap(project_dir: str, out_dir: str | None = None) -> BuildResult:
    """Extract the project's data as one JSON document at
    `<out_dir>/data.json`. Equivalent to `mood tap <project_dir>`.

    Paths must be absolute. `out_dir` is optional; leave it unset to use the
    default under `<project_dir>/.another-mood/`. On errors the document is
    not written.
    """
    overrides = _project_overrides(project_dir)
    if out_dir is not None:
        overrides["tap_dir"] = _absolute_arg("out_dir", out_dir)
    config = ProjectConfig(**overrides)  # type: ignore[arg-type]
    config.verify()
    return command.tap(config)


@mcp.tool()
def init(project_dir: str) -> ScaffoldResult:
    """Initialize a project at `project_dir` from the `starter` blueprint.
    Equivalent to `mood init <project_dir>`.

    Paths must be absolute. The directory is created if missing; unrelated
    files in it are fine. Fails without writing anything if it already holds
    a project.
    """
    return command.init(_absolute_arg("project_dir", project_dir))


@mcp.tool()
def list_blueprints() -> Sequence[Blueprint]:
    """List the bundled blueprints (sample projects).
    Equivalent to `mood blueprint list`.
    """
    return command.list_blueprints()


@mcp.tool()
def apply_blueprint(name: str, project_dir: str) -> ScaffoldResult:
    """Apply the named blueprint by copying its sources into `project_dir`.
    Equivalent to `mood blueprint apply <name> <project_dir>`.

    `name` must be one of the names returned by `list_blueprints()`, and
    paths must be absolute. The directory is created if missing; unrelated
    files in it are fine. Fails without writing anything if it already holds
    a project.
    """
    available = [b.name for b in command.list_blueprints()]
    if name not in available:
        raise ValueError(
            f"unknown blueprint: {name!r} (available: {', '.join(available)})"
        )
    return command.apply_blueprint(name, _absolute_arg("project_dir", project_dir))


# -- Helpers -----------------------------------------------------------------


def _project_overrides(project_dir: str) -> dict[str, object]:
    """Bind the config fields that locate the project, as absolute paths.

    The namespace root is the project itself, so output lands at
    `<project_dir>/.another-mood/` — the one place an agent that named
    `project_dir` is certain to be able to read back. Anchoring on the
    server's CWD instead would hand the agent paths it cannot resolve, and
    reject every project outside a directory it never chose.
    """
    project = _absolute_arg("project_dir", project_dir)
    return {"namespace_root": project, "project_dir": project}


def _absolute_arg(name: str, path: str) -> Path:
    """Require an absolute path argument, and hand it on as given.

    A relative one cannot be resolved here: the base would be this process's
    working directory, which the MCP client chose and the calling agent
    cannot see.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError(f"{name} must be an absolute path, got {path!r}")
    return candidate


def main() -> None:
    basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
    mcp.run()
