"""Project configuration — the invocation parameters and the values the caller
injected (source layout is not configuration; see :mod:`another_mood.layout`)."""

import os
from collections.abc import Iterator
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_VARS_ENV_PREFIX = "MOOD_VARS_"


class ConfigValidationError(Exception):
    """Raised when ProjectConfig fails post-construction validation."""


def _vars_from_env() -> dict[str, str]:
    """Read the `MOOD_VARS_*` environment variables, envelope stripped:
    `MOOD_VARS_GIT_SHA` becomes `git_sha`."""
    return {
        name.removeprefix(_VARS_ENV_PREFIX).lower(): value
        for name, value in os.environ.items()
        if name.startswith(_VARS_ENV_PREFIX) and name != _VARS_ENV_PREFIX
    }


class ProjectConfig(BaseSettings):
    """Project configuration for Another Mood.

    Default output paths derive from `<namespace_root>/.another-mood/<project_dir>/`.
    Environment variables (MOOD_ prefix) override defaults.

    Paths are taken as given: nothing here reads the process CWD, so every
    path must be absolute already (``verify`` enforces it). Absolutizing —
    and thereby choosing what relative paths mean — belongs to the CLI / MCP
    boundary that owns the caller's standing position.
    """

    model_config = SettingsConfigDict(env_prefix="MOOD_")

    # The directory the derived `.another-mood/` tree hangs from, and the base
    # the tree is namespaced by. The CLI binds it to the current directory, the
    # MCP server to project_dir (which collapses the namespacing tail).
    #
    # Bound by the boundary layer, not configured by the user: no CLI option
    # and no MCP argument sets it, and MOOD_NAMESPACE_ROOT never takes effect,
    # since both boundaries pass the field explicitly and init arguments
    # outrank environment sources. Move the output instead — out_dir /
    # site_dir / tap_dir reach every path this would move, one at a time.
    namespace_root: Path

    project_dir: Path

    # Output (published). Unset (None) means "not published"; build and watch
    # fill or drop these per mode (see resolved_for_build / resolved_for_watch).
    out_dir: Path | None = Field(default=None)
    site_dir: Path | None = Field(default=None)

    # Tap document destination directory. Unset (None) resolves to the
    # ``.another-mood/<project>`` default (see resolved_for_tap).
    tap_dir: Path | None = Field(default=None)

    # Working dir. Unset (None) resolves to a fresh system-temp dir at the
    # command layer; set MOOD_TMP_DIR to pin it to a fixed path.
    tmp_dir: Path | None = Field(default=None)

    # Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5077)

    # Caller-injected values, for templates to query by key. The CLI / MCP
    # channels add onto what the environment supplied here.
    vars: dict[str, str] = Field(default_factory=_vars_from_env)

    def resolved_for_build(self) -> "ProjectConfig":
        """Fill unset out_dir/site_dir with the ``.another-mood/<project>`` defaults."""
        rb = _another_mood_root(self.namespace_root, self.project_dir)
        return self.model_copy(
            update={
                "out_dir": self.out_dir or rb / "output",
                "site_dir": self.site_dir or rb / "site",
            }
        )

    def resolved_for_tap(self) -> "ProjectConfig":
        """Fill an unset tap_dir with the ``.another-mood/<project>`` default.

        An explicit tap_dir skips even deriving the default, which would
        require project_dir under namespace_root.
        """
        if self.tap_dir is not None:
            return self
        rb = _another_mood_root(self.namespace_root, self.project_dir)
        return self.model_copy(update={"tap_dir": rb / "tap"})

    def resolved_for_watch(self) -> "ProjectConfig":
        """Drop site_dir — watch never publishes HTML — and keep out_dir as given."""
        return self.model_copy(update={"site_dir": None})

    def verify(self) -> None:
        """Run post-construction checks. Raises ConfigValidationError on failure."""
        relative = {name: path for name, path in _paths(self) if not path.is_absolute()}
        if relative:
            listing = ", ".join(f"{name}={path}" for name, path in relative.items())
            raise ConfigValidationError(
                "Paths must be absolute, but these are relative: "
                f"{listing}. MOOD_* environment variables are read as given, so "
                "they have to be written as absolute paths."
            )
        if not self.project_dir.is_relative_to(self.namespace_root):
            raise ConfigValidationError(
                "Project directory must be under the namespace root "
                f"({self.namespace_root}), but points outside it: {self.project_dir}"
            )
        if not self.project_dir.is_dir():
            raise ConfigValidationError(
                f"Project directory not found: {self.project_dir}"
            )


def _paths(config: ProjectConfig) -> Iterator[tuple[str, Path]]:
    """Yield the config's set path fields as (field name, value) pairs."""
    return (
        (name, value)
        for name, value in config
        if isinstance(value, Path)  # skips the unset (None) ones
    )


def _another_mood_root(namespace_root: Path, project_dir: Path) -> Path:
    """Resolve the `<namespace_root>/.another-mood/<project_dir>/` base directory.

    Output is namespaced by the project's namespace_root-relative path so
    distinct projects never collide. ``ProjectConfig.verify`` guarantees
    ``project_dir`` lies under ``namespace_root``, so ``relative_to`` always
    yields a relative tail — which also sidesteps pathlib's ``/`` swallowing
    the LHS whenever the RHS has an anchor (a naive ``root / ".another-mood" /
    project_dir`` would otherwise land output inside a rooted project itself).
    A project at the root itself collapses the tail, giving
    ``<namespace_root>/.another-mood/``.
    """
    tail = project_dir.relative_to(namespace_root)
    return namespace_root / ".another-mood" / tail
