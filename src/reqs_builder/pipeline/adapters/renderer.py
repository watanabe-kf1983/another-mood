"""Hugo renderer adapter — low-level Hugo operations.

Adapts reqs-builder output to Hugo conventions:
- Renames index.md → _index.md (Hugo branch bundle requirement)
"""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

_HUGO_SOURCE_DIR = files("reqs_builder.resources") / "hugo"


def prepare(src_dir: Path, out_dir: Path) -> None:
    """Copy src_dir to out_dir, renaming index.md → _index.md."""
    shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)
    for index_file in out_dir.rglob("index.md"):
        index_file.rename(index_file.with_name("_index.md"))


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
        ],
        check=True,
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
        ],
    )
