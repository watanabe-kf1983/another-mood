"""Stage — pipeline stage base class, standard implementation, and composite."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from reqs_builder.adapters.watcher import Watcher


class Stage(ABC):
    """A pipeline stage with run (one-shot) and start_watching (dev mode)."""

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def start_watching(self) -> AbstractContextManager[None]: ...


@dataclass(frozen=True)
class NormalStage(Stage):
    """Standard stage: run function + Watcher."""

    run_fn: Callable[[], None]
    watch_paths: Sequence[Path]
    name: str = "Build"

    def run(self) -> None:
        """Run the stage once."""
        self.run_fn()
        print(f"{self.name} complete.", flush=True)

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Initial run + watch in background. Cleans up on exit."""
        self.run()

        thread = threading.Thread(
            target=lambda: Watcher(self.watch_paths, self.run).run(),
            daemon=True,
        )
        thread.start()
        yield


class Pipeline(Stage):
    """Composite stage: runs a sequence of stages as one."""

    def __init__(self, stages: Sequence[Stage]) -> None:
        self._stages = stages

    def run(self) -> None:
        """Run all stages sequentially."""
        for stage in self._stages:
            stage.run()

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Start all stages watching. Cleans up all on exit."""
        with ExitStack() as stack:
            for stage in self._stages:
                stack.enter_context(stage.start_watching())
            yield
