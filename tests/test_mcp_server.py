"""Tests for mcp_server — the agent-facing surface."""

from collections.abc import Callable
from pathlib import Path

import pytest

from another_mood import command, mcp_server
from another_mood.components.shared.tool_version import tool_version
from another_mood.mcp_server import mcp


def test_initialize_announces_another_moods_own_version() -> None:
    # `version` defaults to the empty string and is announced as-is, so
    # dropping the constructor argument would silently strip the version from
    # the initialize response rather than raise.
    # The second assertion keeps the first from passing vacuously if
    # `tool_version()` ever yields the same empty string as the default.
    assert mcp.version == tool_version() != ""


def test_build_roots_output_inside_the_project_dir(tmp_path: Path) -> None:
    """The MCP binding: namespace_root is project_dir, so output lands in it.

    tmp_path sits outside the server's CWD — a project the containment check
    used to reject, and against which a CWD-relative out_dir would have been
    unresolvable for the agent that named the project.
    """
    project = tmp_path / "proj"
    command.init(project)

    result = mcp_server.build(project_dir=str(project))

    assert not result.has_errors()
    assert Path(result.out_dir) == project / ".another-mood" / "output"


_OUTPUT_DIR_CALLS: list[tuple[Callable[[str], object], str]] = [
    (lambda project: mcp_server.build(project_dir=project, out_dir="out"), "out_dir"),
    (
        lambda project: mcp_server.build(project_dir=project, site_dir="site"),
        "site_dir",
    ),
    (lambda project: mcp_server.tap(project_dir=project, out_dir="out"), "out_dir"),
]


class TestRelativePathsAreRejected:
    """Relative paths would resolve against the server's working directory —
    the MCP client's choice, invisible to the calling agent — so every tool
    rejects them instead of aiming at a directory neither side picked.
    """

    @pytest.mark.parametrize(
        "call",
        [
            lambda: mcp_server.build(project_dir="docs"),
            lambda: mcp_server.tap(project_dir="docs"),
            lambda: mcp_server.init(project_dir="docs"),
            lambda: mcp_server.apply_blueprint(name="starter", project_dir="docs"),
        ],
        ids=["build", "tap", "init", "apply_blueprint"],
    )
    def test_project_dir(self, call: Callable[[], object]) -> None:
        with pytest.raises(ValueError, match="project_dir must be an absolute path"):
            call()

    @pytest.mark.parametrize(
        ("call", "rejected"),
        _OUTPUT_DIR_CALLS,
        ids=["build:out_dir", "build:site_dir", "tap:out_dir"],
    )
    def test_output_dirs(
        self, call: Callable[[str], object], rejected: str, tmp_path: Path
    ) -> None:
        # An absolute project_dir gets past the first check, so the failure
        # pins the output argument rather than repeating the one above.
        with pytest.raises(ValueError, match=f"{rejected} must be an absolute path"):
            call(str(tmp_path))
