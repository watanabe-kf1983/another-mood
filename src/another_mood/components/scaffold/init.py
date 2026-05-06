"""Project initialization — generate scaffold directories and sample data."""

import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_TEMPLATE = "starter"


class UnknownTemplateError(Exception):
    """Raised when the requested template name does not exist."""

    def __init__(self, name: str, available: Sequence[str]) -> None:
        self.name = name
        self.available = tuple(available)
        super().__init__(
            f"unknown template: {name!r} (available: {', '.join(available)})"
        )


def _showcase_root() -> Path:
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_showcase"
    if packaged.is_dir():
        return packaged
    # Editable install: showcase lives in the repo, not inside the package.
    return pkg_root.parent.parent / "showcase"


def available_templates() -> Mapping[str, Path]:
    """Return built-in templates as a name → directory mapping.

    Each subdirectory of the bundled ``showcase/`` tree is exposed as a
    template under its own directory name (e.g. ``starter``,
    ``ecommerce``).
    """
    root = _showcase_root()
    if not root.is_dir():
        return {}
    return {entry.name: entry for entry in sorted(root.iterdir()) if entry.is_dir()}


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


def init_project(project_dir: Path, template: str = DEFAULT_TEMPLATE) -> bool:
    """Scaffold *project_dir* from the named built-in template.

    Raises :class:`UnknownTemplateError` if *template* is not a known
    template name.  See :func:`available_templates` for the list.
    """
    templates = available_templates()
    if template not in templates:
        raise UnknownTemplateError(template, sorted(templates))
    return scaffold_project(templates[template], project_dir)
