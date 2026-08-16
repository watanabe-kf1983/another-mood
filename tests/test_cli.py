"""Tests for cli — the terminal-facing surface."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from another_mood import command
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


class TestScaffoldingPaths:
    """The CLI absolutizes the path it is handed, and reports back relative."""

    def test_relative_project_dir_is_resolved_against_the_current_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "sub/proj"])
        assert result.exit_code == 0
        # The title comes from the resolved directory, not from the text typed.
        manifest = (tmp_path / "sub" / "proj" / "sbdb.yaml").read_text()
        assert "title: proj\n" in manifest
        assert "created: sub/proj/sbdb.yaml" in result.output

    def test_dot_project_dir_takes_its_title_from_the_current_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "my-proj"
        project.mkdir()
        monkeypatch.chdir(project)
        result = runner.invoke(app, ["init", "."])
        assert result.exit_code == 0
        assert "title: my-proj\n" in (project / "sbdb.yaml").read_text()

    def test_project_dir_outside_the_current_directory_is_reported_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # resolve() so the expectation matches on platforms where the temp
        # root is itself a symlink (macOS /var -> /private/var).
        elsewhere = (tmp_path / "elsewhere").resolve()
        here = tmp_path / "here"
        here.mkdir()
        monkeypatch.chdir(here)
        result = runner.invoke(app, ["init", str(elsewhere)])
        assert result.exit_code == 0
        # Nothing shorter is available, so the absolute path stands.
        assert f"created: {elsewhere / 'sbdb.yaml'}" in result.output


def test_injected_values_from_both_channels_reach_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOOD_VARS_CI_RUN_URL", "https://ci.test/7")
    command.init(tmp_path / "proj")

    result = runner.invoke(
        app, ["build", "proj", "--var", "CI.Run_ID=7", "--var", "token=abc=def"]
    )

    assert result.exit_code == 0
    output = tmp_path / ".another-mood" / "proj" / "output"
    colophon = (output / "__build_info" / "index.md").read_text(encoding="utf-8")
    # Names are taken as written, and only the first `=` splits. The page
    # escapes the one left in the value.
    assert "| `vars.CI.Run_ID` | 7 |" in colophon
    assert r"| `vars.token` | abc\=def |" in colophon
    # Injecting from the command line leaves what the environment injected.
    assert r"| `vars.ci_run_url` | https\:\/\/ci\.test\/7 |" in colophon


@pytest.mark.parametrize("assignment", ["channel", "=orphan"], ids=["no-=", "no-name"])
def test_a_malformed_var_stops_the_run_before_the_project_is_looked_at(
    assignment: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No project at "proj": reaching it would report that instead.
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["build", "proj", "--var", assignment])
    assert result.exit_code == 1
    assert "--var must be written as NAME=VALUE" in result.output
