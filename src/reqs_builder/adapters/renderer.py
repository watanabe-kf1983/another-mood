"""Hugo renderer adapter — bridges reqs-builder pipeline to Hugo.

Adapts reqs-builder output to Hugo conventions:
- Renames index.md → _index.md (Hugo branch bundle requirement)
"""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from reqs_builder.config import ProjectConfig

_HUGO_SOURCE_DIR = files("reqs_builder.resources") / "hugo"


def prepare_hugo_content(out_dir: Path, hugo_content_dir: Path) -> None:
    """Copy outDir to hugo_content_dir, renaming index.md → _index.md."""
    if hugo_content_dir.exists():
        shutil.rmtree(hugo_content_dir)

    shutil.copytree(out_dir, hugo_content_dir)

    for index_file in hugo_content_dir.rglob("index.md"):
        index_file.rename(index_file.with_name("_index.md"))


def render_build(paths: ProjectConfig) -> None:
    """Run hugo build to generate static HTML from outDir to render_out_dir."""
    assert paths.out_dir is not None
    assert paths.render_out_dir is not None
    assert paths.hugo_content_dir is not None

    prepare_hugo_content(paths.out_dir, paths.hugo_content_dir)

    subprocess.run(
        [
            "hugo",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(paths.hugo_content_dir.resolve()),
            "--destination",
            str(paths.render_out_dir.resolve()),
        ],
        check=True,
    )


def render_dev(config: ProjectConfig) -> subprocess.Popen[bytes]:
    """Start hugo server for live preview. Returns the Popen process."""
    assert config.out_dir is not None
    assert config.hugo_content_dir is not None

    prepare_hugo_content(config.out_dir, config.hugo_content_dir)

    return subprocess.Popen(
        [
            "hugo",
            "server",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(config.hugo_content_dir.resolve()),
            "--port",
            str(config.port),
        ],
    )
