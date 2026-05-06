"""MCP server entry point for AI agents.

Started by MCP clients (e.g. VSCode Copilot Chat, Claude Code) as a stdio
subprocess. Not for direct human use; the `mood` CLI is the human-facing entry.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("another-mood")


@mcp.tool()
def ping() -> str:
    """Connectivity check. Returns a unique signature string to verify the MCP server is reachable."""
    return "ping-pong-song"


def main() -> None:
    mcp.run()
