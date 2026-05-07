"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

import sys
from logging import INFO, basicConfig
from typing import Sequence

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FileResource
from mcp.types import ResourceLink
from pydantic import AnyUrl

from another_mood import command

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
def ping() -> str:
    """Connectivity check. Returns a unique signature string to verify the MCP server is reachable."""
    return "ping-pong-song"


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


def main() -> None:
    basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
    mcp.run()
