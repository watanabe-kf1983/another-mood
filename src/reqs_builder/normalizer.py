"""Normalizer — validate and normalize input data.

Phase 5-4: passthrough (copy only). Validation and normalization in Phase 6.
"""

import shutil
from pathlib import Path


def normalize(src_dir: Path, out_dir: Path) -> None:
    """Copy src_dir to out_dir as-is."""
    shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)
