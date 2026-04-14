"""Hugo renderer adapter — low-level Hugo operations.

Adapts another-mood output to Hugo conventions:
- Renames index.md → _index.md (Hugo branch bundle requirement)
- Replaces deleted .md files with a placeholder so Hugo's dev server
  reflects the removal (Hugo keeps deleted pages in memory otherwise)
"""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from filelock import FileLock

_HUGO_SOURCE_DIR = files("another_mood.resources") / "hugo"

_DELETED_CONTENT = "[This page has been removed. Go to top page.](/)\n"


def prepare(src_dir: Path, out_dir: Path) -> None:
    """Sync src_dir to out_dir, renaming index.md → _index.md.

    Files present in out_dir but absent from src_dir are overwritten
    with a placeholder instead of being deleted, because Hugo's dev
    server keeps deleted pages in memory.
    """
    lock_path = out_dir.parent / f"{out_dir.name}.lock"
    with FileLock(lock_path):
        old_files: set[str] = _collect_md_files(out_dir) if out_dir.exists() else set()
        # Build expected file set: src files with index.md → _index.md rename
        src_files = {
            p.replace("index.md", "_index.md") if p.endswith("index.md") else p
            for p in _collect_md_files(src_dir)
        }
        shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)
        for index_file in out_dir.rglob("index.md"):
            index_file.rename(index_file.with_name("_index.md"))
        for deleted in old_files - src_files:
            deleted_path = out_dir / deleted
            deleted_path.parent.mkdir(parents=True, exist_ok=True)
            deleted_path.write_text(_DELETED_CONTENT)


def _collect_md_files(directory: Path) -> set[str]:
    """Collect relative paths of .md files in a directory."""
    return {str(p.relative_to(directory)) for p in directory.rglob("*.md")}


def build(content_dir: Path, out_dir: Path) -> None:
    """Run renderer build to generate static HTML."""
    subprocess.run(
        [
            "hugo",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(content_dir.resolve()),
            "--destination",
            str(out_dir.resolve()),
            "--logLevel",
            "error",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def serve(content_dir: Path, port: int) -> subprocess.Popen[bytes]:
    """Start renderer dev server for live preview. Returns the Popen process."""
    return subprocess.Popen(
        [
            "hugo",
            "server",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(content_dir.resolve()),
            "--port",
            str(port),
            "--renderToMemory",
            "--logLevel",
            "error",
        ],
        stdout=subprocess.DEVNULL,
    )
