"""Source layout — where a project's source files live."""

from dataclasses import dataclass, fields
from pathlib import Path

from another_mood.components.shared.user_error import UserError


@dataclass(frozen=True)
class SourceLayout:
    schema_file: Path
    reports_file: Path
    contents_dir: Path
    queries_dir: Path
    templates_dir: Path

    def verify(self) -> None:
        """Raise SourceLayoutError listing every path missing on disk."""
        paths = [(f.name, getattr(self, f.name)) for f in fields(self)]
        missing = [
            (name, path)
            for name, path in paths
            if not (path.is_file() if name.endswith("_file") else path.is_dir())
        ]
        if missing:
            lines = [f"  {name}: {path}" for name, path in missing]
            raise SourceLayoutError("Source paths not found:\n" + "\n".join(lines))


class SourceLayoutError(UserError):
    """Missing source paths — a pre-pipeline refusal, never a build-report error."""


def resolve_layout(project_dir: Path) -> SourceLayout:
    """Resolve and verify: raises SourceLayoutError listing missing source paths."""
    # Future dispatch point for format-generation-dependent layouts (sbdb_version).
    definition = project_dir / "definition"
    layout = SourceLayout(
        schema_file=definition / "schema.yaml",
        reports_file=definition / "reports.yaml",
        contents_dir=project_dir / "contents",
        queries_dir=definition / "queries",
        templates_dir=definition / "templates",
    )
    layout.verify()
    return layout
