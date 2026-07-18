"""Tests for preparation — Hugo content sync + prepare_render Component."""

from pathlib import Path
from typing import Any

import yaml

from another_mood.pipeline.adapters.preparation import prepare_render, sync


def _write(path: Path, content: str = "# Hello\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


class TestSync:
    def test_copies_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        sync(src, out)

        assert (out / "a.md").read_text() == "# Hello\n"

    def test_renames_index_to_underscore_index(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "index.md")
        out = tmp_path / "out"

        sync(src, out)

        assert (out / "_index.md").exists()
        assert not (out / "index.md").exists()

    def test_renames_nested_index(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "sub" / "index.md")
        out = tmp_path / "out"

        sync(src, out)

        assert (out / "sub" / "_index.md").exists()
        assert not (out / "sub" / "index.md").exists()

    def test_deleted_file_gets_placeholder(self, tmp_path: Path) -> None:
        """File in out_dir but not in src_dir → overwritten with placeholder."""
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        # First sync: a.md and b.md
        _write(src / "b.md")
        sync(src, out)
        assert (out / "b.md").read_text() == "# Hello\n"

        # Second sync: b.md removed from src
        (src / "b.md").unlink()
        sync(src, out)

        assert (
            out / "b.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"
        assert (out / "a.md").read_text() == "# Hello\n"

    def test_deleted_nested_file_gets_placeholder(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "index.md")
        _write(src / "sub" / "page.md")
        out = tmp_path / "out"

        sync(src, out)
        assert (out / "sub" / "page.md").exists()

        # Remove sub/page.md from src
        (src / "sub" / "page.md").unlink()
        (src / "sub").rmdir()
        sync(src, out)

        assert (
            out / "sub" / "page.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"

    def test_deleted_index_gets_placeholder(self, tmp_path: Path) -> None:
        """_index.md (renamed from index.md) should get placeholder when removed."""
        src = tmp_path / "src"
        _write(src / "index.md")
        _write(src / "sub" / "index.md")
        out = tmp_path / "out"

        sync(src, out)
        assert (out / "_index.md").exists()
        assert (out / "sub" / "_index.md").exists()

        # Remove sub/index.md from src
        (src / "sub" / "index.md").unlink()
        (src / "sub").rmdir()
        sync(src, out)

        assert (
            out / "sub" / "_index.md"
        ).read_text() == "[This page has been removed. Go to top page.](/)\n"

    def test_deleted_blob_is_unlinked(self, tmp_path: Path) -> None:
        """A removed blob (non-.md) is unlinked, not overwritten with the page
        placeholder — a Markdown body at a byte path would corrupt it."""
        src = tmp_path / "src"
        _write(src / "index.md")
        _write(src / "blob" / "cover.png", "PNGBYTES")
        out = tmp_path / "out"

        sync(src, out)
        assert (out / "blob" / "cover.png").read_text() == "PNGBYTES"

        (src / "blob" / "cover.png").unlink()
        sync(src, out)

        assert not (out / "blob" / "cover.png").exists()
        assert (out / "_index.md").read_text() == "# Hello\n"

    def test_no_placeholder_when_nothing_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _write(src / "a.md")
        _write(src / "b.md")
        out = tmp_path / "out"

        sync(src, out)
        sync(src, out)

        assert (out / "a.md").read_text() == "# Hello\n"
        assert (out / "b.md").read_text() == "# Hello\n"

    def test_first_sync_no_crash(self, tmp_path: Path) -> None:
        """First sync with no existing out_dir should work."""
        src = tmp_path / "src"
        _write(src / "a.md")
        out = tmp_path / "out"

        sync(src, out)

        assert (out / "a.md").exists()

    def test_deleted_content_override(self, tmp_path: Path) -> None:
        """Caller-supplied deleted_content replaces the default placeholder."""
        src = tmp_path / "src"
        _write(src / "a.md")
        _write(src / "b.md")
        out = tmp_path / "out"

        sync(src, out)
        (src / "b.md").unlink()
        sync(src, out, deleted_content="# Error\n")

        assert (out / "b.md").read_text() == "# Error\n"
        assert (out / "a.md").read_text() == "# Hello\n"


class TestPrepareRender:
    def test_upstream_error_replaces_deleted_pages_with_build_report(
        self, tmp_path: Path
    ) -> None:
        """On upstream error, previously-rendered pages get the build-report body."""
        data_dir = tmp_path / "upstream"
        out_dir = tmp_path / "out"

        # Previous successful run: out_dir has a regular page.
        _write(out_dir / "data" / "foo.md")

        # Upstream now carries an error + the build-report index.md from reconcile.
        _write_yaml(
            data_dir / "reports" / "__build_report.yaml",
            {"__build_report": {"errors": [{"message": "boom"}]}},
        )
        _write(data_dir / "data" / "index.md", "# Build Failed\n\nboom\n")

        prepare_render(data_dir=data_dir, out_dir=out_dir)

        assert (
            out_dir / "data" / "_index.md"
        ).read_text() == "# Build Failed\n\nboom\n"
        assert (out_dir / "data" / "foo.md").read_text() == "# Build Failed\n\nboom\n"
