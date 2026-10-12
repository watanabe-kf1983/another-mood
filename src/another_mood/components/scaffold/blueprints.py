"""Blueprint enumeration and project scaffolding.

A *blueprint* is a built-in sample project that ``mood blueprint apply``
copies into a target directory.  Blueprints are declared in
``showcase/index.yaml`` (the manifest) under a top-level ``blueprints:``
list of ``{name, description}`` records; the directory of each blueprint
lives at ``showcase/<name>/``.
"""

import shutil
import textwrap
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Sequence, cast

import yaml

from another_mood.components.shared.tool_version import tool_homepage, tool_version

DEFAULT_BLUEPRINT = "starter"
INDEX_FILE = "index.yaml"
# Kept in sync with components/manifest (a cross-component import would
# violate the dependency rule: components may only depend on shared).
MANIFEST_FILENAME = "sbdb.yaml"
SBDB_VERSION = 1
README_FILENAME = "README.md"


@dataclass(frozen=True)
class Blueprint:
    """A bundled sample project entry from the manifest."""

    name: str
    description: str


@dataclass(frozen=True)
class ScaffoldResult:
    """Outcome of a scaffolding pass: the files that were created."""

    created: Sequence[Path]


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

    Overwrites whatever it lands on: guarding the target directory is the
    caller's job.  The template's own manifest is not copied.  A README.md
    pointing at Another Mood is generated only where none exists, since one
    may predate the project (a freshly cloned repository).
    """
    template_files = _collect_template_files(template_root)
    for rel in template_files:
        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_root / rel, dest)
    manifest = project_dir / MANIFEST_FILENAME
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(_generate_manifest(project_dir), encoding="utf-8")
    readme = project_dir / README_FILENAME
    readme_absent = not readme.exists()
    if readme_absent:
        readme.write_text(_generate_readme(project_dir), encoding="utf-8")
    return ScaffoldResult(
        created=[
            *(project_dir / rel for rel in template_files),
            manifest,
            *([readme] if readme_absent else []),
        ]
    )


def _collect_template_files(template_root: Path) -> Sequence[Path]:
    return sorted(
        p.relative_to(template_root)
        for p in template_root.rglob("*")
        if p.is_file() and p.relative_to(template_root) != Path(MANIFEST_FILENAME)
    )


def _generate_manifest(project_dir: Path) -> str:
    # A verified floor ("known to work"), not an audited true minimum.
    running = tool_version()
    return yaml.safe_dump(
        {
            "sbdb_version": SBDB_VERSION,
            "title": _project_title(project_dir),
            "tools": {"another-mood": {"minimum_version": running}},
        },
        sort_keys=False,
        allow_unicode=True,
    )


def _generate_readme(project_dir: Path) -> str:
    # A pointer for readers who do not know `mood` yet: what manages the
    # directory, how to get it, and where the command's own help starts.
    # Structure and workflow stay out; `mood --help` and the docs own them.
    return textwrap.dedent(f"""\
        # {_project_title(project_dir)}

        A source-based database managed by [Another Mood]({tool_homepage()}):
        the YAML and Markdown files here are the sources, and `mood build` turns them into
        Markdown and HTML pages that stay in sync with each other.

            uv tool install another-mood    # or: pipx install another-mood
            mood build <path to this directory>

        `mood --help` lists the commands. `mood docs list` and `mood docs read <uri>` open the bundled manual.
        """)


def _project_title(project_dir: Path) -> str:
    # resolve() folds any `..` before the last component is read off it.
    return project_dir.resolve().name
