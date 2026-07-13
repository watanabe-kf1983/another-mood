"""Workspace — the working environment for one pipeline run."""

from dataclasses import dataclass
from pathlib import Path

from another_mood.components.shared.component.component import ComponentCall
from another_mood.config import ProjectConfig
from another_mood.pipeline.base import ComponentOutput


@dataclass(frozen=True)
class Workspace:
    """A pipeline run's config paired with the scratch root its stages work under.

    Threaded through every stage: components read their inputs from ``config``
    and write their outputs under ``root`` (via :meth:`component_output`).
    """

    config: ProjectConfig
    root: Path

    def component_output(self, component: ComponentCall) -> ComponentOutput:
        """Return ComponentOutput for the given component under ``root``."""
        path = self.root / component.name
        path.mkdir(parents=True, exist_ok=True)
        return ComponentOutput(path)
