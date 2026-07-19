"""Tests for transfer — hardlink-based file transport between pipeline directories."""

import os
from pathlib import Path

import pytest

from another_mood.components.shared.transfer import link_or_copy, transfer_tree


class TestLinkOrCopy:
    def test_links_to_the_same_inode(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("payload", encoding="utf-8")
        dst = tmp_path / "dst.txt"

        link_or_copy(src, dst)

        assert dst.read_text(encoding="utf-8") == "payload"
        assert dst.stat().st_ino == src.stat().st_ino

    def test_replaces_dst_without_writing_into_it(self, tmp_path: Path) -> None:
        """An observer hardlinked to the old dst keeps its bytes."""
        src = tmp_path / "src.txt"
        src.write_text("new", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        dst.write_text("old", encoding="utf-8")
        observer = tmp_path / "observer.txt"
        os.link(dst, observer)

        link_or_copy(src, dst)

        assert dst.read_text(encoding="utf-8") == "new"
        assert observer.read_text(encoding="utf-8") == "old"

    def test_falls_back_to_copy_when_link_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse_link(src: object, dst: object) -> None:
            raise OSError("simulated cross-device link")

        monkeypatch.setattr(os, "link", refuse_link)
        src = tmp_path / "src.txt"
        src.write_text("payload", encoding="utf-8")
        dst = tmp_path / "dst.txt"

        link_or_copy(src, dst)

        assert dst.read_text(encoding="utf-8") == "payload"
        assert dst.stat().st_ino != src.stat().st_ino


class TestTransferTree:
    def test_mirrors_a_nested_tree_by_hardlink(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_text("a", encoding="utf-8")
        (src / "sub" / "b.txt").write_text("b", encoding="utf-8")
        dst = tmp_path / "dst"

        transfer_tree(src, dst)

        assert (dst / "a.txt").stat().st_ino == (src / "a.txt").stat().st_ino
        assert (dst / "sub" / "b.txt").stat().st_ino == (
            src / "sub" / "b.txt"
        ).stat().st_ino

    def test_merges_into_an_existing_tree(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("new", encoding="utf-8")
        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "a.txt").write_text("old", encoding="utf-8")
        (dst / "kept.txt").write_text("kept", encoding="utf-8")

        transfer_tree(src, dst, dirs_exist_ok=True)

        assert (dst / "a.txt").read_text(encoding="utf-8") == "new"
        assert (dst / "kept.txt").read_text(encoding="utf-8") == "kept"
