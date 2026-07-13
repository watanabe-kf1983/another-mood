"""Project configuration and path resolution."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigValidationError(Exception):
    """Raised when ProjectConfig fails post-construction validation."""


class ProjectConfig(BaseSettings):
    """Project configuration for Another Mood.

    Default values use `project_dir` as base for input paths
    and `.another-mood/<project_dir>/` for output paths.
    Environment variables (RB_ prefix) override defaults.
    """

    model_config = SettingsConfigDict(env_prefix="RB_")

    project_dir: Path

    # Input (user-edited)
    schema_file: Path = Field(default=Path(""))
    reports_file: Path = Field(default=Path(""))
    contents_dir: Path = Field(default=Path(""))
    queries_dir: Path = Field(default=Path(""))
    templates_dir: Path = Field(default=Path(""))

    # Output (published). Unset (None) means "not published"; build and watch
    # fill or drop these per mode (see resolved_for_build / resolved_for_watch).
    out_dir: Path | None = Field(default=None)
    render_dir: Path | None = Field(default=None)

    # Working dir. Unset (None) resolves to a fresh system-temp dir at the
    # command layer; set RB_TMP_DIR to pin it to a fixed path.
    tmp_dir: Path | None = Field(default=None)

    # Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5077)

    def resolved_for_build(self) -> "ProjectConfig":
        """Fill unset out_dir/render_dir with the ``.another-mood/<project>`` defaults."""
        rb = _another_mood_root(self.project_dir)
        return self.model_copy(
            update={
                "out_dir": self.out_dir or rb / "output",
                "render_dir": self.render_dir or rb / "render",
            }
        )

    def resolved_for_watch(self) -> "ProjectConfig":
        """Drop render_dir — watch never publishes HTML — and keep out_dir as given."""
        return self.model_copy(update={"render_dir": None})

    def verify(self) -> None:
        """Run post-construction checks. Raises ConfigValidationError on failure."""
        if not self.project_dir.is_dir():
            raise ConfigValidationError(
                f"Project directory not found: {self.project_dir}"
            )
        dir_sources = {
            "contents_dir": self.contents_dir,
            "queries_dir": self.queries_dir,
            "templates_dir": self.templates_dir,
        }
        file_sources = {
            "schema_file": self.schema_file,
            "reports_file": self.reports_file,
        }
        missing = [(name, p) for name, p in dir_sources.items() if not p.is_dir()] + [
            (name, p) for name, p in file_sources.items() if not p.is_file()
        ]
        if missing:
            lines = [f"  {name}: {p}" for name, p in missing]
            raise ConfigValidationError("Source paths not found:\n" + "\n".join(lines))

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        pd = Path(values.get("project_dir", ""))
        if not values.get("schema_file"):
            values["schema_file"] = pd / "definition" / "schema.yaml"
        if not values.get("reports_file"):
            values["reports_file"] = pd / "definition" / "reports.yaml"
        if not values.get("contents_dir"):
            values["contents_dir"] = pd / "contents"
        if not values.get("queries_dir"):
            values["queries_dir"] = pd / "definition" / "queries"
        if not values.get("templates_dir"):
            values["templates_dir"] = pd / "definition" / "templates"
        return values


def _another_mood_root(project_dir: Path) -> Path:
    """Resolve the `.another-mood/<project_dir>/` base directory.

    Pathlib's ``/`` swallows the LHS whenever the RHS has an anchor (drive
    and/or root), so a naive ``Path(".another-mood") / project_dir`` would
    silently land tmp / output inside the project itself when a rooted
    ``project_dir`` is passed (e.g. from an MCP agent). Project a relative
    tail off CWD when possible; fall back to the basename for paths that
    lie outside CWD.

    ``anchor`` (rather than ``is_absolute()``) is the discriminator: on
    Windows, ``/some/path`` and ``C:foo`` both have an anchor yet are not
    absolute, and pathlib still swallows the LHS for them.
    """
    if not project_dir.anchor:
        return Path(".another-mood") / project_dir
    try:
        tail = project_dir.relative_to(Path.cwd())
    except ValueError:
        tail = Path(project_dir.name)
    return Path(".another-mood") / tail
