"""Tests for renderer.prepare — Hugo content sync."""

from pathlib import Path

from another_mood.pipeline.adapters.renderer import prepare


def _write(path: Path, content: str = "# Hello\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestPrepare:
    def test_copies_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        prepare(src, out)

        assert (out / "a.md").read_text() == "# Hello\n"

    def test_renames_index_to_underscore_index(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "index.md")
        out = tmp_path / "out"

        prepare(src, out)

        assert (out / "_index.md").exists()
        assert not (out / "index.md").exists()

    def test_renames_nested_index(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "sub" / "index.md")
        out = tmp_path / "out"

        prepare(src, out)

        assert (out / "sub" / "_index.md").exists()
        assert not (out / "sub" / "index.md").exists()

    def test_deleted_file_gets_placeholder(self, tmp_path: Path) -> None:
        """File in out_dir but not in src_dir → overwritten with placeholder."""
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        # First prepare: a.md and b.md
        _write(src / "b.md")
        prepare(src, out)
        assert (out / "b.md").read_text() == "# Hello\n"

        # Second prepare: b.md removed from src
        (src / "b.md").unlink()
        prepare(src, out)

        assert (
            out / "b.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"
        assert (out / "a.md").read_text() == "# Hello\n"

    def test_deleted_nested_file_gets_placeholder(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "index.md")
        _write(src / "sub" / "page.md")
        out = tmp_path / "out"

        prepare(src, out)
        assert (out / "sub" / "page.md").exists()

        # Remove sub/page.md from src
        (src / "sub" / "page.md").unlink()
        (src / "sub").rmdir()
        prepare(src, out)

        assert (
            out / "sub" / "page.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"

    def test_deleted_index_gets_placeholder(self, tmp_path: Path) -> None:
        """_index.md (renamed from index.md) should get placeholder when removed."""
        src = tmp_path / "src"
        _write(src / "index.md")
        _write(src / "sub" / "index.md")
        out = tmp_path / "out"

        prepare(src, out)
        assert (out / "_index.md").exists()
        assert (out / "sub" / "_index.md").exists()

        # Remove sub/index.md from src
        (src / "sub" / "index.md").unlink()
        (src / "sub").rmdir()
        prepare(src, out)

        assert (
            out / "sub" / "_index.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"

    def test_no_placeholder_when_nothing_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "a.md")
        _write(src / "b.md")
        out = tmp_path / "out"

        prepare(src, out)
        prepare(src, out)

        assert (out / "a.md").read_text() == "# Hello\n"
        assert (out / "b.md").read_text() == "# Hello\n"

    def test_first_prepare_no_crash(self, tmp_path: Path) -> None:
        """First prepare with no existing out_dir should work."""
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        prepare(src, out)

        assert (out / "a.md").exists()
