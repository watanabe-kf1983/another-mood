"""Project configuration and path resolution."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectConfig(BaseSettings):
    """Project configuration for reqs-builder.

    Default values use `project_dir` as base for input paths
    and `.reqs-builder/<project_dir>/` for output paths.
    Environment variables (RB_ prefix) override defaults.
    """

    model_config = SettingsConfigDict(env_prefix="RB_")

    project_dir: Path

    # Input (user-edited)
    contents_dir: Path = Field(default=Path(""))

    # Output (generated)
    out_dir: Path = Field(default=Path(""))
    render_out_dir: Path = Field(default=Path(""))
    hugo_content_dir: Path = Field(default=Path(""))

    # Server
    port: int = Field(default=1313)

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        pd = Path(values.get("project_dir", ""))
        rb = Path(".reqs-builder") / pd
        if not values.get("contents_dir"):
            values["contents_dir"] = pd / "contents"
        if not values.get("out_dir"):
            values["out_dir"] = rb / "output"
        if not values.get("render_out_dir"):
            values["render_out_dir"] = rb / "render"
        if not values.get("hugo_content_dir"):
            values["hugo_content_dir"] = rb / "hugo-content"
        return values
