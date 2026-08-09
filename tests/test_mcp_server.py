"""Tests for mcp_server — the agent-facing surface."""

from another_mood.components.shared.tool_version import tool_version
from another_mood.mcp_server import mcp


def test_initialize_announces_another_moods_own_version() -> None:
    # Guards a private-attribute assignment: FastMCP exposes no `version`
    # seam, and the low-level Server silently falls back to the MCP SDK's
    # version, so a regression here announces a plausible wrong version
    # instead of raising.
    options = mcp._mcp_server.create_initialization_options()  # pyright: ignore[reportPrivateUsage]
    assert options.server_version == tool_version()
