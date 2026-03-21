"""Build command — passthrough copy of contents to output, then render with Hugo."""

import shutil

from reqs_builder.adapters.renderer import render_build
from reqs_builder.config import ProjectConfig


def build(paths: ProjectConfig) -> None:
    """Copy contents_dir to out_dir, then render to HTML."""
    assert paths.contents_dir is not None
    assert paths.out_dir is not None

    if paths.out_dir.exists():
        shutil.rmtree(paths.out_dir)

    shutil.copytree(paths.contents_dir, paths.out_dir)
    render_build(paths)
