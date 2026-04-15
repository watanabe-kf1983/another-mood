"""Project initialization — generate scaffold directories and sample data."""

import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Sequence


def _template_dir() -> Path:
    return Path(str(resources.files("another_mood.resources") / "init_template"))


def _collect_template_files(template_root: Path) -> Sequence[Path]:
    """Return all files under *template_root* as relative paths, sorted."""
    return sorted(
        p.relative_to(template_root) for p in template_root.rglob("*") if p.is_file()
    )


def scaffold_project(template_root: Path, project_dir: Path) -> bool:
    """Copy *template_root* into *project_dir*, skipping existing files.

    Existing files are never overwritten — a warning is printed and the
    file is skipped.  Returns ``True`` when every file was written
    successfully (no skips).
    """
    files = _collect_template_files(template_root)

    all_written = True
    for rel in files:
        dest = project_dir / rel
        if dest.exists():
            print(f"warning: skipped (already exists): {dest}", file=sys.stderr)
            all_written = False
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_root / rel, dest)
        print(f"  created: {dest}", file=sys.stderr)

    return all_written


def init_project(project_dir: Path) -> bool:
    """Scaffold *project_dir* with the built-in template."""
    return scaffold_project(_template_dir(), project_dir)
