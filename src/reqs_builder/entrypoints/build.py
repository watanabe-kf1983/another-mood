"""Build command — passthrough copy of contents to output."""

import shutil

from reqs_builder.config import ProjectPaths


def build(paths: ProjectPaths) -> None:
    """Copy contents_dir to out_dir (clean build)."""
    assert paths.contents_dir is not None
    assert paths.out_dir is not None

    if paths.out_dir.exists():
        shutil.rmtree(paths.out_dir)

    shutil.copytree(paths.contents_dir, paths.out_dir)
