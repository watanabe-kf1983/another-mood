"""Blueprint enumeration and project scaffolding.

A *blueprint* is a built-in sample project that ``mood blueprint apply``
copies into a target directory.  Blueprints are declared in
``showcase/index.yaml`` (the manifest) under a top-level ``blueprints:``
list of ``{name, description}`` records; the directory of each blueprint
lives at ``showcase/<name>/``.
"""

import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Sequence, cast

import yaml

DEFAULT_BLUEPRINT = "starter"
INDEX_FILE = "index.yaml"


@dataclass(frozen=True)
class Blueprint:
    """A bundled sample project entry from the manifest."""

    name: str
    description: str


@dataclass(frozen=True)
class ScaffoldResult:
    """Outcome of a scaffolding pass: which files were created vs. skipped."""

    created: Sequence[Path]
    skipped: Sequence[Path]

    @property
    def all_written(self) -> bool:
        return not self.skipped


def _showcase_root() -> Path:
    """Return the directory containing the bundled blueprints."""
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_showcase"
    if packaged.is_dir():
        return packaged
    # Editable install: showcase lives in the repo, not inside the package.
    return pkg_root.parent.parent / "showcase"


def available_blueprints() -> Sequence[Blueprint]:
    """Return the bundled blueprint manifest in declared order."""
    return load_blueprints(_showcase_root())


def load_blueprints(root: Path) -> Sequence[Blueprint]:
    """Read ``<root>/index.yaml`` and return its blueprint entries.

    Trusts the file's shape since the manifest is shipped with the
    package; relies on ``read_text`` / ``yaml.safe_load`` to raise on a
    missing or syntactically broken file.
    """
    raw = yaml.safe_load((root / INDEX_FILE).read_text(encoding="utf-8"))
    entries = cast(Sequence[dict[str, str]], raw["blueprints"])
    return [Blueprint(name=e["name"], description=e["description"]) for e in entries]


def apply_blueprint(name: str, project_dir: Path) -> ScaffoldResult:
    """Copy the named blueprint's directory into *project_dir*.

    The caller is responsible for validating *name* against
    :func:`available_blueprints`.
    """
    return scaffold_project(_showcase_root() / name, project_dir)


def scaffold_project(template_root: Path, project_dir: Path) -> ScaffoldResult:
    """Copy *template_root* into *project_dir*, skipping existing files.

    Existing files are never overwritten.  Returns a :class:`ScaffoldResult`
    listing both the destinations that were created and those that were
    skipped because the file already existed.
    """
    created: list[Path] = []
    skipped: list[Path] = []
    for rel in _collect_template_files(template_root):
        dest = project_dir / rel
        if dest.exists():
            skipped.append(dest)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_root / rel, dest)
        created.append(dest)
    return ScaffoldResult(created=created, skipped=skipped)


def _collect_template_files(template_root: Path) -> Sequence[Path]:
    return sorted(
        p.relative_to(template_root) for p in template_root.rglob("*") if p.is_file()
    )
