"""Tests for cli — the terminal-facing surface."""

from typer.testing import CliRunner

from another_mood.cli import app
from another_mood.components.shared.tool_version import tool_version

runner = CliRunner()


def test_version_option_prints_the_command_name_and_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"mood {tool_version()}"


def test_version_option_needs_no_subcommand() -> None:
    # The option is eager, so it must resolve during parsing rather than fall
    # through to typer's "Missing command." error.
    result = runner.invoke(app, ["--version"])
    assert "Missing command" not in result.output
