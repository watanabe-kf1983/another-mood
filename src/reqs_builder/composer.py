"""Composer — combine normalized data into views.

Phase 5-5: passthrough (copy only). YAML DSL query evaluation in Phase 6.
"""

import shutil
from pathlib import Path


def compose(src_dir: Path, out_dir: Path) -> None:
    """Copy src_dir to out_dir as-is."""
    shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)
