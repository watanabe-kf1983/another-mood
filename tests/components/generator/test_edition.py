"""Tests for edition — ReportsSchema validation and reports.yaml parsing."""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.generator.data_tree import wrap_tree
from another_mood.components.generator.edition import (
    Edition,
    load_editions,
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
        load_editions(_write(tmp_path, source))


# ── parse ──────────────────────────────────────────────────────────


def test_load_with_entries(tmp_path: Path) -> None:
    # Form A yields a single implicit edition named "default".
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
    assert load_editions(path) == (
        Edition(name="default", file_per=("erds.item", "erds.item.entities.item")),
    )


def test_load_empty_file_per(tmp_path: Path) -> None:
    assert load_editions(_write(tmp_path, "file_per: []\n")) == (
        Edition(name="default", file_per=()),
    )


# ── is_split_target ────────────────────────────────────────────────


def test_is_split_target_listed() -> None:
    edition = Edition(file_per=("erds.item", "erds.item.entities.item"))
    assert edition.is_split_target("erds.item")
    assert edition.is_split_target("erds.item.entities.item")


def test_is_split_target_not_listed() -> None:
    edition = Edition(file_per=("erds.item",))
    assert not edition.is_split_target("screens.item")
    # A prefix of a listed id is not itself a target.
    assert not edition.is_split_target("erds")


def test_is_split_target_empty_file_per() -> None:
    assert not Edition(file_per=()).is_split_target("erds.item")


# ── page_path ──────────────────────────────────────────────────────


class TestPagePath:
    """``page_path`` formats the page-owning node's path.

    Finding that node (self / ancestor / none) is ``nearest_ancestor``'s
    contract (see its tests); here we only pin what page_path itself
    adds: the ``None`` -> ``index.md`` mapping and the
    ``{anchor_path sans leading /}.md`` formatting, plus that the split
    predicate is keyed on ``object_type_id`` against ``file_per``.
    """

    _TREE = {"erds": [{"id": "user-mgmt", "entities": [{"id": "user"}]}]}

    def test_no_split_boundary_is_index(self) -> None:
        # Empty file_per -> nearest_ancestor finds nothing -> index.md.
        root = wrap_tree(self._TREE)
        assert Edition(file_per=()).page_path(root["erds"][0]) == "index.md"

    def test_match_formats_anchor_path_as_md(self) -> None:
        # object_type_id "erds.item" is in file_per, so the erd is its own
        # page: leading "/" dropped, inner "/" kept (removeprefix, not
        # lstrip), ".md" appended.
        root = wrap_tree(self._TREE)
        erd = root["erds"][0]
        assert Edition(file_per=("erds.item",)).page_path(erd) == "erds/user-mgmt.md"
