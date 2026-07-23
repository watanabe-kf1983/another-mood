"""Source layout — where a project's source files live."""

from collections.abc import Iterator
from dataclasses import dataclass, fields
from pathlib import Path

from another_mood.components.shared.user_error import UserError


@dataclass(frozen=True)
class SourceLayout:
    definition_dir: Path
    schema_file: Path
    reports_file: Path
    contents_dir: Path
    queries_dir: Path
    templates_dir: Path

    def verify(self) -> None:
        """Raise SourceLayoutError for paths missing on disk, then for
        unknown entries under ``definition_dir``."""
        self._verify_paths_exist()
        self._verify_definition_entries()

    def _verify_paths_exist(self) -> None:
        missing = [
            (name, path)
            for name, path in self._paths()
            if not (path.is_file() if name.endswith("_file") else path.is_dir())
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


def resolve_layout(project_dir: Path) -> SourceLayout:
    """Resolve and verify: raises SourceLayoutError for missing or unknown source paths."""
    # Future dispatch point for format-generation-dependent layouts (sbdb_version).
    definition = project_dir / "definition"
    layout = SourceLayout(
        definition_dir=definition,
        schema_file=definition / "schema.yaml",
        reports_file=definition / "reports.yaml",
        contents_dir=project_dir / "contents",
        queries_dir=definition / "queries",
        templates_dir=definition / "templates",
    )
    layout.verify()
    return layout
