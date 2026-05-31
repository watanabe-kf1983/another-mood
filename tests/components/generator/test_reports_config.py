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
