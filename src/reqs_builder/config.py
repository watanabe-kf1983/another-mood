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
    definition_dir: Path = Field(default=Path(""))
    schema_dir: Path = Field(default=Path(""))
    contents_dir: Path = Field(default=Path(""))
    queries_dir: Path = Field(default=Path(""))
    templates_dir: Path = Field(default=Path(""))

    # Output (generated)
    data_catalog_dir: Path = Field(default=Path(""))
    normalized_contents_dir: Path = Field(default=Path(""))
    normalized_queries_dir: Path = Field(default=Path(""))
    views_dir: Path = Field(default=Path(""))
    out_dir: Path = Field(default=Path(""))
    render_out_dir: Path = Field(default=Path(""))
    render_in_dir: Path = Field(default=Path(""))

    # Server
    port: int = Field(default=1313)

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        pd = Path(values.get("project_dir", ""))
        rb = Path(".reqs-builder") / pd
        if not values.get("definition_dir"):
            values["definition_dir"] = pd / "definition"
        if not values.get("schema_dir"):
            values["schema_dir"] = pd / "definition" / "schema"
        if not values.get("contents_dir"):
            values["contents_dir"] = pd / "contents"
        if not values.get("queries_dir"):
            values["queries_dir"] = pd / "definition" / "queries"
        if not values.get("templates_dir"):
            values["templates_dir"] = pd / "definition" / "templates"
        if not values.get("data_catalog_dir"):
            values["data_catalog_dir"] = rb / "tmp" / "data-catalog"
        if not values.get("normalized_contents_dir"):
            values["normalized_contents_dir"] = rb / "tmp" / "normalized" / "contents"
        if not values.get("normalized_queries_dir"):
            values["normalized_queries_dir"] = rb / "tmp" / "normalized" / "queries"
        if not values.get("views_dir"):
            values["views_dir"] = rb / "tmp" / "views"
        if not values.get("out_dir"):
            values["out_dir"] = rb / "output"
        if not values.get("render_out_dir"):
            values["render_out_dir"] = rb / "render"
        if not values.get("render_in_dir"):
            values["render_in_dir"] = rb / "tmp" / "render-input"
        return values
