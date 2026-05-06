"""Blueprint enumeration and project scaffolding.

A *blueprint* is a built-in sample project that ``mood blueprint apply``
copies into a target directory.  Blueprints are declared in
``showcase/index.yaml`` (the manifest) as ``<name>: <description>``
entries; the directory of each blueprint lives at ``showcase/<name>/``.
"""

import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Mapping, Sequence, cast

import yaml

DEFAULT_BLUEPRINT = "starter"
INDEX_FILE = "index.yaml"


def _showcase_root() -> Path:
    """Return the directory containing the bundled blueprints."""
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_showcase"
    if packaged.is_dir():
        return packaged
    # Editable install: showcase lives in the repo, not inside the package.
    return pkg_root.parent.parent / "showcase"


def available_blueprints() -> Mapping[str, str]:
    """Return the bundled blueprint manifest as name → description."""
    return load_blueprints(_showcase_root())


def load_blueprints(root: Path) -> Mapping[str, str]:
    """Read ``<root>/index.yaml`` and return its blueprint entries.

    Trusts the file's shape since the manifest is shipped with the
    package; relies on ``read_text`` / ``yaml.safe_load`` to raise on a
    missing or syntactically broken file.
    """
    raw: object = yaml.safe_load((root / INDEX_FILE).read_text(encoding="utf-8"))
    return cast(Mapping[str, str], raw)


def apply_blueprint(name: str, project_dir: Path) -> bool:
    """Copy the named blueprint's directory into *project_dir*.

    The caller is responsible for validating *name* against
    :func:`available_blueprints`.
    """
    return scaffold_project(_showcase_root() / name, project_dir)


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


def _collect_template_files(template_root: Path) -> Sequence[Path]:
    return sorted(
        p.relative_to(template_root) for p in template_root.rglob("*") if p.is_file()
    )
