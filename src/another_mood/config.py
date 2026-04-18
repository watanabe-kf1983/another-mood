"""Project configuration and path resolution."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from another_mood.components.shared.component import ComponentCall
from another_mood.components.shared.component_output import ComponentOutput


class ConfigValidationError(Exception):
    """Raised when ProjectConfig fails post-construction validation."""


class ProjectConfig(BaseSettings):
    """Project configuration for another-mood.

    Default values use `project_dir` as base for input paths
    and `.another-mood/<project_dir>/` for output paths.
    Environment variables (RB_ prefix) override defaults.
    """

    model_config = SettingsConfigDict(env_prefix="RB_")

    project_dir: Path

    # Input (user-edited)
    schema_dir: Path = Field(default=Path(""))
    contents_dir: Path = Field(default=Path(""))
    queries_dir: Path = Field(default=Path(""))
    templates_dir: Path = Field(default=Path(""))

    # Output (generated)
    tmp_dir: Path = Field(default=Path(""))
    out_dir: Path = Field(default=Path(""))
    render_dir: Path = Field(default=Path(""))

    # Server
    port: int = Field(default=1313)

    def component_output(self, component: ComponentCall) -> ComponentOutput:
        """Return ComponentOutput for the given component under tmp_dir."""
        path = self.tmp_dir / component.name
        path.mkdir(parents=True, exist_ok=True)
        return ComponentOutput(path)

    def tmp_subdir(self, *parts: str) -> Path:
        """Return tmp_dir/<parts>, creating it if missing."""
        path = self.tmp_dir.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def verify(self) -> None:
        """Run post-construction checks. Raises ConfigValidationError on failure."""
        if not self.project_dir.is_dir():
            raise ConfigValidationError(
                f"Project directory not found: {self.project_dir}"
            )
        sources = {
            "schema_dir": self.schema_dir,
            "contents_dir": self.contents_dir,
            "queries_dir": self.queries_dir,
            "templates_dir": self.templates_dir,
        }
        missing = [(name, p) for name, p in sources.items() if not p.is_dir()]
        if missing:
            lines = [f"  {name}: {p}" for name, p in missing]
            raise ConfigValidationError(
                "Source directories not found:\n" + "\n".join(lines)
            )

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        pd = Path(values.get("project_dir", ""))
        rb = Path(".another-mood") / pd
        if not values.get("schema_dir"):
            values["schema_dir"] = pd / "definition" / "schema"
        if not values.get("contents_dir"):
            values["contents_dir"] = pd / "contents"
        if not values.get("queries_dir"):
            values["queries_dir"] = pd / "definition" / "queries"
        if not values.get("templates_dir"):
            values["templates_dir"] = pd / "definition" / "templates"
        if not values.get("tmp_dir"):
            values["tmp_dir"] = rb / "tmp"
        if not values.get("out_dir"):
            values["out_dir"] = rb / "output"
        if not values.get("render_dir"):
            values["render_dir"] = rb / "render"
        return values
