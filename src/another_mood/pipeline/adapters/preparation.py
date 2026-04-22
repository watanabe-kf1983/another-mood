"""Hugo content preparation — Component that syncs reconcile output to a Hugo-ready form.

Adapts another-mood output to Hugo conventions:
- Renames index.md → _index.md (Hugo branch bundle requirement)
- Replaces deleted .md files with a placeholder so Hugo's dev server
  reflects the removal (Hugo keeps deleted pages in memory otherwise)

exclusive_write=False: Hugo's live server watches this dir, so in-place
incremental updates are preferred over atomic clear-and-replace.

error_propagation=False: reconcile renders a __build_report page on
upstream error, which Hugo must still serve. The sync runs unconditionally,
while error_propagation is invoked manually to forward upstream reports to
out_dir/reports where build_report_stage collects them.
"""

import shutil
from pathlib import Path

from another_mood.components.shared.component import Component
from another_mood.components.shared.dir_lock import dir_lock
from another_mood.components.shared.errors import error_propagation

_DELETED_CONTENT = "[This page has been removed. Go to top page.](/)\n"


@Component(
    out_dir="out_dir",
    upstream_dirs=["data_dir"],
    exclusive_write=False,
    error_propagation=False,
)
def prepare_render(data_dir: Path, *, out_dir: Path) -> None:
    """Sync reconcile data into a Hugo-ready content directory."""
    with error_propagation(
        [data_dir], out_dir, component="prepare_render"
    ) as data_dirs:
        if data_dirs is not None:
            sync(data_dirs.upstreams[0], data_dirs.out)
        else:
            sync(data_dir / "data", out_dir / "data")


def sync(src_dir: Path, out_dir: Path) -> None:
    """Sync src_dir to out_dir, renaming index.md → _index.md.

    Files present in out_dir but absent from src_dir are overwritten with
    a placeholder so Hugo's dev server does not keep the deleted pages
    in memory.
    """
    with dir_lock(out_dir):
        old_files: set[str] = _collect_md_files(out_dir) if out_dir.exists() else set()
        src_files = {
            p.replace("index.md", "_index.md") if p.endswith("index.md") else p
            for p in _collect_md_files(src_dir)
        }
        out_dir.mkdir(parents=True, exist_ok=True)
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
