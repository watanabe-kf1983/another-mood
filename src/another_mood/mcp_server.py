"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping, cast

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FileResource
from mcp.types import ResourceLink
from pydantic import AnyUrl

CATALOG_FILE = "mcp-resources.yaml"

MIME_TYPES: Mapping[str, str] = {
    ".md": "text/markdown",
    ".yaml": "application/yaml",
}


@dataclass(frozen=True)
class _DocEntry:
    uri: str
    name: str
    description: str
    mime_type: str
    path: Path


mcp = FastMCP("another-mood")


@mcp.tool()
def ping() -> str:
    """Connectivity check. Returns a unique signature string to verify the MCP server is reachable."""
    return "ping-pong-song"


@mcp.tool()
def list_docs() -> list[ResourceLink]:
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
        for e in _ENTRIES.values()
    ]


@mcp.tool()
def read_doc(uri: str) -> str:
    """Read a bundled Another Mood document by its `docs://` URI.

    `uri` must be one of the values returned by `list_docs()` (e.g.
    `docs://reference/cli.md`).  Returns the raw file contents as text.
    """
    entry = _ENTRIES.get(uri)
    if entry is None:
        raise ValueError(
            f"Unknown doc URI: {uri!r}. Call list_docs() to see available URIs."
        )
    return entry.path.read_text(encoding="utf-8")


def _docs_root() -> Path:
    """Return the directory containing the bundled docs/ tree."""
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_docs"
    if packaged.is_dir():
        return packaged
    # Editable install: docs/ lives in the repo, not inside the package.
    return pkg_root.parent.parent / "docs"


def _load_entries(docs_root: Path) -> Mapping[str, _DocEntry]:
    raw = cast(
        Mapping[str, list[Mapping[str, str]]],
        yaml.safe_load((docs_root / CATALOG_FILE).read_text(encoding="utf-8")),
    )
    entries: dict[str, _DocEntry] = {}
    for e in raw["resources"]:
        rel = e["path"]
        uri = f"docs://{rel}"
        entries[uri] = _DocEntry(
            uri=uri,
            name=rel,
            description=e["description"].strip(),
            mime_type=MIME_TYPES[Path(rel).suffix],
            path=(docs_root / rel).resolve(),
        )
    return entries


def _register_resources() -> None:
    for entry in _ENTRIES.values():
        mcp.add_resource(
            FileResource(
                uri=AnyUrl(entry.uri),
                name=entry.name,
                description=entry.description,
                mime_type=entry.mime_type,
                path=entry.path,
            )
        )


_ENTRIES = _load_entries(_docs_root())
_register_resources()


def main() -> None:
    mcp.run()
