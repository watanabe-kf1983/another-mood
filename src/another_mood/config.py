"""Project configuration — invocation parameters only (source layout is not
configuration; see :mod:`another_mood.layout`)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigValidationError(Exception):
    """Raised when ProjectConfig fails post-construction validation."""


class ProjectConfig(BaseSettings):
    """Project configuration for Another Mood.

    Default output paths derive from `.another-mood/<project_dir>/`.
    Environment variables (RB_ prefix) override defaults.
    """

    model_config = SettingsConfigDict(env_prefix="RB_")

    project_dir: Path

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
        cwd = Path.cwd().resolve()
        if not self.project_dir.resolve().is_relative_to(cwd):
            raise ConfigValidationError(
                "Project directory must be under the current directory "
                f"({cwd}), but points outside it: {self.project_dir}"
            )
        if not self.project_dir.is_dir():
            raise ConfigValidationError(
                f"Project directory not found: {self.project_dir}"
            )


def _another_mood_root(project_dir: Path) -> Path:
    """Resolve the `.another-mood/<project_dir>/` base directory.

    Output is namespaced by the project's CWD-relative path so distinct
    projects never collide. ``ProjectConfig.verify`` guarantees
    ``project_dir`` resolves under CWD, so ``relative_to`` always yields a
    relative tail — which also sidesteps pathlib's ``/`` swallowing the LHS
    whenever the RHS has an anchor (a naive ``Path(".another-mood") /
    project_dir`` would otherwise land output inside a rooted project itself).
    """
    tail = project_dir.resolve().relative_to(Path.cwd().resolve())
    return Path(".another-mood") / tail
