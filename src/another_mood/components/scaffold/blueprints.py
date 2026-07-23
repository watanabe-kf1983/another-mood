"""Blueprint enumeration and project scaffolding.

A *blueprint* is a built-in sample project that ``mood blueprint apply``
copies into a target directory.  Blueprints are declared in
``showcase/index.yaml`` (the manifest) under a top-level ``blueprints:``
list of ``{name, description}`` records; the directory of each blueprint
lives at ``showcase/<name>/``.
"""

import shutil
from dataclasses import dataclass
from importlib import metadata, resources
from pathlib import Path
from typing import Sequence, cast

import yaml

from another_mood.components.shared.user_error import UserError

DEFAULT_BLUEPRINT = "starter"
INDEX_FILE = "index.yaml"
# Kept in sync with components/manifest (a cross-component import would
# violate the dependency rule: components may only depend on shared).
MANIFEST_FILENAME = "sbdb.yaml"
SBDB_VERSION = 1


@dataclass(frozen=True)
class Blueprint:
    """A bundled sample project entry from the manifest."""

    name: str
    description: str


@dataclass(frozen=True)
class ScaffoldResult:
    """Outcome of a scaffolding pass: the files that were created."""

    created: Sequence[Path]


class ScaffoldConflictError(UserError):
    """A file the scaffold would write already exists; nothing was written."""

    def __init__(self, conflicts: Sequence[Path]) -> None:
        self.conflicts = conflicts
        listing = "\n".join(f"  {path}" for path in conflicts)
        super().__init__(f"refusing to scaffold: these files already exist:\n{listing}")


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
    """Copy *template_root* into *project_dir* and generate a fresh manifest.

    The template's own manifest is not copied.  Raises
    :class:`ScaffoldConflictError` before writing anything if any
    destination file already exists; unrelated existing files are fine.
    """
    targets = [
        *(project_dir / rel for rel in _collect_template_files(template_root)),
        project_dir / MANIFEST_FILENAME,
    ]
    if conflicts := [dest for dest in targets if dest.exists()]:
        raise ScaffoldConflictError(conflicts)
    for rel in _collect_template_files(template_root):
        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_root / rel, dest)
    manifest = project_dir / MANIFEST_FILENAME
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(_generate_manifest(project_dir), encoding="utf-8")
    return ScaffoldResult(created=targets)


def _collect_template_files(template_root: Path) -> Sequence[Path]:
    return sorted(
        p.relative_to(template_root)
        for p in template_root.rglob("*")
        if p.is_file() and p.relative_to(template_root) != Path(MANIFEST_FILENAME)
    )


def _generate_manifest(project_dir: Path) -> str:
    # resolve() so `mood init .` gets the real directory name — the same
    # derivation as the build's fallback title.
    title = project_dir.resolve().name
    # A verified floor ("known to work"), not an audited true minimum.
    running = metadata.version("another-mood")
    return yaml.safe_dump(
        {
            "sbdb_version": SBDB_VERSION,
            "title": title,
            "tools": {"another-mood": {"minimum_version": running}},
        },
        sort_keys=False,
        allow_unicode=True,
    )
