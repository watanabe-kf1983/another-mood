"""Tests for edition — ReportsSchema validation and reports.yaml parsing."""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.generator.data_tree import wrap_tree
from another_mood.components.generator.edition import (
    Edition,
    PagingPolicy,
    load_editions,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "reports.yaml"
    path.write_text(source)
    return path


def _named(name: str) -> Edition:
    """A minimal Edition for name-derived tests (dir_segment / is_system);
    its paging and templates_dir are irrelevant here."""
    return Edition(paging=PagingPolicy(), name=name, templates_dir=Path("t"))


# ── validation ─────────────────────────────────────────────────────

_INVALID_REPORTS_CASES = [
    pytest.param("file_per: erds.item\n", id="file_per not a list"),
    pytest.param("file_per: [123]\n", id="file_per entry not a string"),
    pytest.param("file_per: ['']\n", id="file_per entry empty"),
    pytest.param("file_per: ['a..b']\n", id="file_per entry malformed dotted id"),
    pytest.param("unknown_key: 1\n", id="unknown top-level key"),
    # form A and form B are mutually exclusive (oneOf).
    pytest.param(
        "file_per: [erds.item]\neditions:\n  web:\n    file_per: []\n",
        id="form A and form B mixed",
    ),
    pytest.param("editions: {}\n", id="empty editions map"),
    pytest.param(
        "editions:\n  __meta:\n    file_per: []\n", id="edition name reserved __ prefix"
    ),
    pytest.param(
        "editions:\n  '':\n    file_per: []\n", id="edition name empty string"
    ),
    pytest.param(
        "editions:\n  web:\n    unknown_key: 1\n", id="unknown key in edition entry"
    ),
]


@pytest.mark.parametrize("source", _INVALID_REPORTS_CASES)
def test_load_rejects_invalid(source: str, tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        load_editions(_write(tmp_path, source), tmp_path / "templates")


# ── parse ──────────────────────────────────────────────────────────


def test_load_with_entries(tmp_path: Path) -> None:
    # Form A yields a single implicit edition named "default".
    templates_dir = tmp_path / "templates"
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
    assert load_editions(path, templates_dir) == (
        Edition(
            paging=PagingPolicy(("erds.item", "erds.item.entities.item")),
            name="default",
            templates_dir=templates_dir,
        ),
    )


def test_load_empty_file_per(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    assert load_editions(_write(tmp_path, "file_per: []\n"), templates_dir) == (
        Edition(paging=PagingPolicy(), name="default", templates_dir=templates_dir),
    )


def test_load_form_b_editions(tmp_path: Path) -> None:
    # Form B yields one edition per entry, in declaration order; a missing
    # or empty file_per is the no-split edition.
    templates_dir = tmp_path / "templates"
    path = _write(
        tmp_path,
        dedent(
            """
            editions:
              web:
                file_per:
                  - erds.item
                  - erds.item.entities.item
              pdf:
                file_per: []
            """
        ),
    )
    assert load_editions(path, templates_dir) == (
        Edition(
            paging=PagingPolicy(("erds.item", "erds.item.entities.item")),
            name="web",
            templates_dir=templates_dir,
        ),
        Edition(paging=PagingPolicy(), name="pdf", templates_dir=templates_dir),
    )


# ── dir_segment ────────────────────────────────────────────────────


def test_dir_segment_ascii_safe_name_is_identity() -> None:
    assert _named("web").dir_segment == "web"


def test_dir_segment_escapes_unsafe_name() -> None:
    # Same per-segment escape as anchor_path: URL-unsafe ASCII (space, `/`)
    # is percent-encoded, non-ASCII ucschar (版) is kept raw.
    assert _named("Web 版").dir_segment == "Web%20版"
    assert _named("a/b").dir_segment == "a%2Fb"


# ── is_system ──────────────────────────────────────────────────────


def test_is_system_true_for_dunder_name() -> None:
    # The meta edition mounts at `__db`; the `__` prefix marks a system
    # edition so the cover routes it to ## Database Information.
    assert _named("__db").is_system is True


def test_is_system_false_for_user_and_cover_names() -> None:
    # User edition names are validated non-`__`; the site-root name `""` (the
    # cover render) is not system either.
    assert _named("web").is_system is False
    assert _named("").is_system is False


# ── is_split_target ────────────────────────────────────────────────


def test_is_split_target_listed() -> None:
    paging = PagingPolicy(("erds.item", "erds.item.entities.item"))
    assert paging.is_split_target("erds.item")
    assert paging.is_split_target("erds.item.entities.item")


def test_is_split_target_not_listed() -> None:
    paging = PagingPolicy(("erds.item",))
    assert not paging.is_split_target("screens.item")
    # A prefix of a listed id is not itself a target.
    assert not paging.is_split_target("erds")


def test_is_split_target_empty_file_per() -> None:
    assert not PagingPolicy().is_split_target("erds.item")


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
        assert PagingPolicy().page_path(root["erds"][0]) == "index.md"

    def test_match_formats_anchor_path_as_md(self) -> None:
        # object_type_id "erds.item" is in file_per, so the erd is its own
        # page: leading "/" dropped, inner "/" kept (removeprefix, not
        # lstrip), ".md" appended.
        root = wrap_tree(self._TREE)
        erd = root["erds"][0]
        assert PagingPolicy(("erds.item",)).page_path(erd) == "erds/user-mgmt.md"
