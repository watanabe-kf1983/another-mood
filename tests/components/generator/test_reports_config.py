"""Tests for reports_config — ReportsSchema validation and reports.yaml parsing."""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.generator.reports_config import (
    ReportsConfig,
    load_reports_config,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "reports.yaml"
    path.write_text(source)
    return path


# ── validation ─────────────────────────────────────────────────────

_INVALID_REPORTS_CASES = [
    pytest.param("file_per: erds.item\n", id="file_per not a list"),
    pytest.param("file_per: [123]\n", id="file_per entry not a string"),
    pytest.param("file_per: ['']\n", id="file_per entry empty"),
    pytest.param("file_per: ['a..b']\n", id="file_per entry malformed dotted id"),
    pytest.param("unknown_key: 1\n", id="unknown top-level key"),
]


@pytest.mark.parametrize("source", _INVALID_REPORTS_CASES)
def test_load_rejects_invalid(source: str, tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        load_reports_config(_write(tmp_path, source))


# ── parse ──────────────────────────────────────────────────────────


def test_load_with_entries(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        dedent(
            """
            file_per:
              - erds.item
              - erds.item.entities.item
            """
        ),
    )
    assert load_reports_config(path) == ReportsConfig(
        file_per=("erds.item", "erds.item.entities.item")
    )


def test_load_empty_file_per(tmp_path: Path) -> None:
    assert load_reports_config(_write(tmp_path, "file_per: []\n")) == ReportsConfig(
        file_per=()
    )


# ── is_split_target ────────────────────────────────────────────────


def test_is_split_target_listed() -> None:
    config = ReportsConfig(file_per=("erds.item", "erds.item.entities.item"))
    assert config.is_split_target("erds.item")
    assert config.is_split_target("erds.item.entities.item")


def test_is_split_target_not_listed() -> None:
    config = ReportsConfig(file_per=("erds.item",))
    assert not config.is_split_target("screens.item")
    # A prefix of a listed id is not itself a target.
    assert not config.is_split_target("erds")


def test_is_split_target_empty_file_per() -> None:
    assert not ReportsConfig(file_per=()).is_split_target("erds.item")
