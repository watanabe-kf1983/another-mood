"""Hugo content preparation — Component that syncs reconcile output to a Hugo-ready form.

Adapts Another Mood output to Hugo conventions:
- Renames index.md → _index.md (Hugo branch bundle requirement)
- Replaces deleted .md files with a placeholder so Hugo's dev server
  reflects the removal (Hugo keeps deleted pages in memory otherwise)

exclusive_write=False: Hugo's live server watches this dir, so in-place
incremental updates are preferred over atomic clear-and-replace.

error_propagation=False: reconcile renders a __build_failure page on
upstream error, which Hugo must still serve. The sync runs unconditionally,
while error_propagation is invoked manually to forward upstream reports to
out_dir/reports where build_report_stage collects them.
"""

import shutil
from pathlib import Path

from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.dir_lock import dir_lock
from another_mood.components.shared.component.errors import error_propagation

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
            page = data_dir / "data" / "index.md"
            content = (
                page.read_text(encoding="utf-8") if page.is_file() else _DELETED_CONTENT
            )
            sync(data_dir / "data", out_dir / "data", deleted_content=content)


def sync(
    src_dir: Path, out_dir: Path, *, deleted_content: str = _DELETED_CONTENT
) -> None:
    """Sync src_dir to out_dir, renaming index.md → _index.md.

    Files present in out_dir but absent from src_dir are overwritten with
    deleted_content so Hugo's dev server does not keep the deleted pages
    in memory.
    """
    with dir_lock(out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        old_files = _collect_files(out_dir)
        src_files = {_hugo_name(p) for p in _collect_files(src_dir)}
        for src_file in src_dir.rglob("*"):
            if not src_file.is_file():
                continue
            dst = out_dir / _hugo_name(src_file.relative_to(src_dir))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
        for deleted in old_files - src_files:
            (out_dir / deleted).write_text(deleted_content, encoding="utf-8")


def _hugo_name(rel: Path) -> Path:
    """Apply Hugo's index.md → _index.md rename at the leaf."""
    return rel.with_name("_index.md") if rel.name == "index.md" else rel


def _collect_files(directory: Path) -> set[Path]:
    """Collect relative paths of files in a directory."""
    return {p.relative_to(directory) for p in directory.rglob("*") if p.is_file()}
