"""Build command — passthrough copy of contents to output, then render with Hugo."""

import shutil
from pathlib import Path

from reqs_builder.adapters.renderer import render_build
from reqs_builder.config import ProjectConfig
from reqs_builder.atomic_dir_writer import AtomicDirWriter


def build(paths: ProjectConfig) -> None:
    """Copy contents_dir to out_dir, then render to HTML."""
    assert paths.contents_dir is not None
    assert paths.out_dir is not None
    contents_dir = paths.contents_dir

    def copy(*, out_dir: Path) -> None:
        shutil.copytree(contents_dir, out_dir, dirs_exist_ok=True)

    AtomicDirWriter(paths.out_dir, copy).run()
    render_build(paths)
