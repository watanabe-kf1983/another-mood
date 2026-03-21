"""Path resolution and project configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectPaths(BaseSettings):
    """Resolved paths for a reqs-builder project.

    Default values use `project_dir` as base for input paths
    and `.reqs-builder/<project_dir>/` for output paths.
    Environment variables (RB_ prefix) override defaults.
    """

    model_config = SettingsConfigDict(env_prefix="RB_")

    project_dir: Path

    # Input (user-edited)
    contents_dir: Path | None = Field(default=None)

    # Output (generated)
    out_dir: Path | None = Field(default=None)

    def model_post_init(self, _context: object) -> None:
        if self.contents_dir is None:
            self.contents_dir = self.project_dir / "contents"
        if self.out_dir is None:
            self.out_dir = Path(".reqs-builder") / self.project_dir / "output"
