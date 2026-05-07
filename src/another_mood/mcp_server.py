"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

from importlib import resources
from pathlib import Path
from typing import Mapping, Sequence, cast

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FileResource
from pydantic import AnyUrl

CATALOG_FILE = "mcp-resources.yaml"

MIME_TYPES: Mapping[str, str] = {
    ".md": "text/markdown",
    ".yaml": "application/yaml",
}


mcp = FastMCP("another-mood")


@mcp.tool()
def ping() -> str:
    """Connectivity check. Returns a unique signature string to verify the MCP server is reachable."""
    return "ping-pong-song"


def _docs_root() -> Path:
    """Return the directory containing the bundled docs/ tree."""
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_docs"
    if packaged.is_dir():
        return packaged
    # Editable install: docs/ lives in the repo, not inside the package.
    return pkg_root.parent.parent / "docs"


def _load_catalog(docs_root: Path) -> Sequence[Mapping[str, str]]:
    raw = cast(
        Mapping[str, Sequence[Mapping[str, str]]],
        yaml.safe_load((docs_root / CATALOG_FILE).read_text(encoding="utf-8")),
    )
    return raw["resources"]


def _build_resource(entry: Mapping[str, str], docs_root: Path) -> FileResource:
    rel = entry["path"]
    abs_path = (docs_root / rel).resolve()
    return FileResource(
        uri=AnyUrl(f"docs://{rel}"),
        name=rel,
        description=entry["description"].strip(),
        mime_type=MIME_TYPES[abs_path.suffix],
        path=abs_path,
    )


def _register_resources() -> None:
    docs_root = _docs_root()
    for entry in _load_catalog(docs_root):
        mcp.add_resource(_build_resource(entry, docs_root))


_register_resources()


def main() -> None:
    mcp.run()
