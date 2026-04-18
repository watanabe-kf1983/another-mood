"""ComponentOutput — typed accessor for a component's output directory."""

from dataclasses import dataclass
from pathlib import Path

from another_mood.components.shared.dir_lock import version_path_for


@dataclass(frozen=True)
class ComponentOutput:
    """A component's output directory with derived paths."""

    dir: Path

    @property
    def watch_target_path(self) -> Path:
        """Path to watch for completion of upstream writes."""
        return version_path_for(self.dir)
