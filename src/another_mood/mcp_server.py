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
from another_mood.command import BuildResult
from another_mood.components.scaffold.blueprints import Blueprint, ScaffoldResult
from another_mood.config import ProjectConfig

_INSTRUCTIONS = """\
Another Mood manages a source-based database: a set of YAML and Markdown
files that, when built, generates a synchronized set of Markdown and HTML
documents. Editing a source file in one place keeps every page derived
from it consistent.

The source files live under `<project_dir>/` and fall into four kinds:

- `definition/schema.yaml` declares data types
- `contents/` holds data (YAML records or Markdown prose)
- `definition/queries/` (optional) reshapes data into views
- `definition/templates/` describes output pages

Workflow:

- Start a project: call `list_blueprints` then `apply_blueprint(name,
  project_dir)`. `init(project_dir)` is a shortcut for the default
  starter.
- After editing sources: call `build(project_dir)` and inspect the result.
  The `output/__meta_entity/`, `__table_view/`, and `__meta_query/`
  subdirectories under the build output are auto-generated diagnostic
  views — read them mid-edit to verify how schema, data, and queries
  resolved.
- Before editing schema, query, or template files, consult the reference:
  call `list_docs()` for the catalog, then `read_doc(uri)` with a
  `docs://` URI from the listing.

Another Mood also provides live preview, but not as an MCP tool. Ask the
user to run `mood watch <project_dir>` in a separate terminal.
"""

mcp = FastMCP("another-mood", instructions=_INSTRUCTIONS)

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
def build(
    project_dir: str,
    out_dir: str | None = None,
    render_dir: str | None = None,
) -> BuildResult:
    """Run the Another Mood build pipeline once over `project_dir` and return
    the build result. Equivalent to `mood build <project_dir>`.

    Use this in an edit-build-inspect feedback loop after editing source
    files. The pipeline reads `definition/` and `contents/` under
    `project_dir`; the rendered output directory is reported back in
    `out_dir`.

    `out_dir` and `render_dir` are optional; leave them unset to use the
    defaults under `.another-mood/<project_dir>/`.

    For DSL syntax, see `read_doc()` (catalog via `list_docs()`).
    """
    overrides: dict[str, object] = {"project_dir": Path(project_dir)}
    if out_dir is not None:
        overrides["out_dir"] = Path(out_dir)
    if render_dir is not None:
        overrides["render_dir"] = Path(render_dir)
    config = ProjectConfig(**overrides)  # type: ignore[arg-type]
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
