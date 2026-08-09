"""Tests for tool_version — the single reading of another-mood's own version."""

from importlib import metadata

from packaging.version import Version

from another_mood.components.shared.tool_version import (
    DISTRIBUTION_NAME,
    tool_version,
)


def test_distribution_name_resolves_to_the_package_under_test() -> None:
    # Pins the constant to the distribution that actually ships
    # `another_mood`, the agreement with pyproject.toml's `project.name`
    # that Python itself cannot enforce.
    providers = metadata.packages_distributions()["another_mood"]
    assert DISTRIBUTION_NAME in providers


def test_tool_version_reports_the_installed_version() -> None:
    assert tool_version() == metadata.version(DISTRIBUTION_NAME)


def test_tool_version_is_a_pep_440_version() -> None:
    # The minimum_version gate compares this against a user-declared version
    # with `packaging`, so an unparseable value would break the gate, not just
    # the display.
    assert Version(tool_version())
