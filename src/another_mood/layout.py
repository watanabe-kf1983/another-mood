"""Source layout — where a project's source files live."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import ClassVar

from another_mood.components.manifest import MANIFEST_FILENAME
from another_mood.components.shared.user_error import UserError


@dataclass(frozen=True)
class SourceLayout:
    manifest_file: Path
    definition_dir: Path
    schema_file: Path
    reports_file: Path
    contents_dir: Path
    queries_dir: Path
    templates_dir: Path

    # A build tolerates a missing manifest for as long as "absent means
    # sbdb_version 1" holds; drop once the manifest becomes mandatory.
    OPTIONAL_PATHS: ClassVar[frozenset[str]] = frozenset({"manifest_file"})

    @classmethod
    def for_project(cls, project_dir: Path) -> "SourceLayout":
        """Where each of *project_dir*'s source paths lives."""
        # Future dispatch point for format-generation-dependent layouts:
        # pick the generation's layout here once sbdb_version can vary.
        definition = project_dir / "definition"
        return cls(
            manifest_file=project_dir / MANIFEST_FILENAME,
            definition_dir=definition,
            schema_file=definition / "schema.yaml",
            reports_file=definition / "reports.yaml",
            contents_dir=project_dir / "contents",
            queries_dir=definition / "queries",
            templates_dir=definition / "templates",
        )

    def verify(self) -> None:
        """Raise SourceLayoutError for paths missing on disk, then for
        unknown entries under ``definition_dir``."""
        self._verify_paths_exist()
        self._verify_definition_entries()

    def verify_absent(self) -> None:
        """Raise ProjectExistsError if any of these paths exists on disk,
        :attr:`OPTIONAL_PATHS` included."""
        if existing := sorted(path for _, path in self._paths() if path.exists()):
            raise ProjectExistsError(existing)

    def _verify_paths_exist(self) -> None:
        missing = [
            (name, path)
            for name, path in self._paths()
            if name not in self.OPTIONAL_PATHS
            and not (path.is_file() if name.endswith("_file") else path.is_dir())
        ]
        if missing:
            lines = [f"  {name}: {path}" for name, path in missing]
            raise SourceLayoutError("Source paths not found:\n" + "\n".join(lines))

    def _verify_definition_entries(self) -> None:
        """Reject top-level entries of ``definition_dir`` outside this
        layout's own names, hidden entries excepted."""
        known = frozenset(
            path.name for _, path in self._paths() if path.parent == self.definition_dir
        )
        unknown = sorted(
            entry.name
            for entry in self.definition_dir.iterdir()
            if entry.name not in known and not entry.name.startswith(".")
        )
        if unknown:
            lines = [f"  {name}" for name in unknown]
            raise SourceLayoutError(
                "Unknown entries under definition/:\n"
                + "\n".join(lines)
                + "\nOnly these are read there: "
                + ", ".join(sorted(known))
            )

    def _paths(self) -> Iterator[tuple[str, Path]]:
        return ((f.name, getattr(self, f.name)) for f in fields(self))


class SourceLayoutError(UserError):
    """Unusable source layout — a pre-pipeline refusal, never a build-report error."""


class ProjectExistsError(UserError):
    """The target already holds paths mood writes — a pre-scaffold refusal."""

    def __init__(self, existing: Sequence[Path]) -> None:
        self.existing = existing
        listing = "\n".join(f"  {path}" for path in existing)
        super().__init__(
            "refusing to scaffold into an existing project: "
            f"these already exist and are mood's to write:\n{listing}"
        )


def resolve_layout(project_dir: Path) -> SourceLayout:
    """Resolve and verify: raises SourceLayoutError for missing or unknown source paths."""
    layout = SourceLayout.for_project(project_dir)
    layout.verify()
    return layout


def verify_absent(project_dir: Path) -> None:
    """Resolve and verify absence: the scaffold-side counterpart of
    :func:`resolve_layout`, raising ProjectExistsError if *project_dir*
    already holds a project."""
    SourceLayout.for_project(project_dir).verify_absent()
