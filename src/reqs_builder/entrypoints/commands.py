"""CLI command implementations."""

import threading

from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.stages import pipeline


def build(config: ProjectConfig) -> None:
    """Run all pipeline stages: copy_contents → render."""
    pipeline(config).run()


def dev(config: ProjectConfig) -> None:
    """Start all pipeline stages in watching mode."""
    with pipeline(config).start_watching():
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
