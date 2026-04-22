"""Publish — copy component outputs to their public destination directories."""

import shutil
from collections.abc import Sequence
from pathlib import Path

from another_mood.components.shared.component import Component
from another_mood.components.shared.dir_lock import dir_lock


@Component(out_dir="out_dir", upstream_dirs=["upstream"])
def publish(
    upstream: Path,
    *,
    out_dir: Path,
    src_dirs: Sequence[Path],
    dist_dirs: Sequence[Path],
) -> None:
    """Copy each src_dir to its corresponding dist_dir.

    upstream/out_dir are for the Component framework (error propagation,
    exclusive read/write of reports); actual copies run between src_dirs
    and dist_dirs.
    """
    for src, dist in zip(src_dirs, dist_dirs):
        with dir_lock(src.parent):
            if dist.exists():
                shutil.rmtree(dist)
            shutil.copytree(src, dist)
