"""ComponentOutput — typed accessor for a component's output directory."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ComponentOutput:
    """A component's output directory with derived paths."""

    dir: Path

    @property
    def watch_target_path(self) -> Path:
        """Path to watch for upstream changes."""
        return self.dir
