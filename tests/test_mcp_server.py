"""Tests for mcp_server — the agent-facing surface."""

from another_mood.components.shared.tool_version import tool_version
from another_mood.mcp_server import mcp


def test_initialize_announces_another_moods_own_version() -> None:
    # `version` defaults to the empty string and is announced as-is, so
    # dropping the constructor argument would silently strip the version from
    # the initialize response rather than raise.
    # The second assertion keeps the first from passing vacuously if
    # `tool_version()` ever yields the same empty string as the default.
    assert mcp.version == tool_version() != ""
