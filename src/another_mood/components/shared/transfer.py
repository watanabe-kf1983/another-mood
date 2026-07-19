"""Transfer — move files between pipeline directories by hardlink.

Callers must keep the transported trees write-once: replace a file via
unlink + re-create, never write into an existing file. An in-place write
reaches every directory sharing the inode (including published output)
and fires no watcher event there. Enforced pipeline-wide by
tests/pipeline/test_write_once_sweep.py.
"""

import os
import shutil
from pathlib import Path


def transfer_tree(src: Path, dst: Path, *, dirs_exist_ok: bool = False) -> None:
    """Recursively transfer ``src`` to ``dst`` via :func:`link_or_copy`."""
    shutil.copytree(src, dst, copy_function=link_or_copy, dirs_exist_ok=dirs_exist_ok)


def link_or_copy(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    """Replace ``dst`` with a hardlink to ``src``, or a copy where hardlinks
    cannot work (another filesystem, unsupported FS)."""
    dst_path = Path(dst)
    if dst_path.exists() or dst_path.is_symlink():
        dst_path.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
