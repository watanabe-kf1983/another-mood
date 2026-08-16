"""Workspace — the working environment for one pipeline run."""

from dataclasses import asdict, dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Literal

from another_mood.components.manifest import Manifest
from another_mood.components.shared.build_info import BuildInfo, flatten_build_info
from another_mood.components.shared.component.component import ComponentCall
from another_mood.components.shared.tool_version import PROCESSOR_ID, tool_version
from another_mood.config import ProjectConfig
from another_mood.layout import SourceLayout
from another_mood.pipeline.base import ComponentOutput


type ProcessorCommand = Literal["build", "watch", "tap"]


@dataclass(frozen=True)
class ProcessorInfo:
    """What processed a run, as opposed to what it processed."""

    name: str
    version: str
    started_at: datetime
    command: ProcessorCommand


def make_processor_info(command: ProcessorCommand) -> ProcessorInfo:
    """Read the running processor's identity, stamping the current moment."""
    return ProcessorInfo(
        name=PROCESSOR_ID,
        version=tool_version(),
        started_at=datetime.now().astimezone(),
        command=command,
    )


@dataclass(frozen=True)
class Workspace:
    """A pipeline run's config paired with the scratch root its stages work under.

    Threaded through every stage: components read their source inputs from
    ``layout``, invocation parameters from ``config``, and write their
    outputs under ``root`` (via :meth:`component_output`).
    """

    config: ProjectConfig
    root: Path
    layout: SourceLayout
    # Project identity from sbdb.yaml — separate from config (how to build).
    manifest: Manifest
    processor: ProcessorInfo
    # True when the command layer created root as a throwaway system-temp dir
    # (vs. a user-pinned MOOD_TMP_DIR it must not delete).
    temporary: bool = False

    @cached_property
    def build_info(self) -> BuildInfo:
        return {
            "processor.name": self.processor.name,
            "processor.version": self.processor.version,
            "processor.command": self.processor.command,
            "processor.started_at": self.processor.started_at.isoformat(
                timespec="seconds"
            ),
            # Every invocation parameter, unfiltered: how the run was invoked
            # is the question the colophon answers. `vars` is not one of them
            # and gets its own namespace.
            **flatten_build_info(
                "processor.config", self.config.model_dump(exclude={"vars"})
            ),
            # What the run actually worked in, which config only asks for:
            # an unpinned tmp_dir leaves no config row, but a working dir
            # still exists — and outlives the run when a failure keeps it.
            **flatten_build_info(
                "processor.workspace",
                {"root": self.root, "temporary": self.temporary},
            ),
            **flatten_build_info("vars", self.config.vars),
            # Whole: sbdb.yaml's schema admits no top-level key this misses.
            **flatten_build_info("manifest", asdict(self.manifest)),
        }

    def component_output(self, component: ComponentCall) -> ComponentOutput:
        """Return ComponentOutput for the given component under ``root``."""
        path = self.root / component.name
        path.mkdir(parents=True, exist_ok=True)
        return ComponentOutput(path)
