"""Task — pipeline task base class, standard implementation, and composite."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from reqs_builder.pipeline.adapters.watcher import Watcher


class Task(ABC):
    """A unit of work with run (one-shot) and start_watching (dev mode)."""

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def start_watching(self) -> AbstractContextManager[None]: ...


@dataclass(frozen=True)
class Stage(Task):
    """Standard task: run function + Watcher."""

    run_fn: Callable[[], None]
    watch_paths: Sequence[Path]

    def run(self) -> None:
        """Run the stage once."""
        self.run_fn()

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


class Pipeline(Task):
    """Composite task: runs a sequence of tasks as one."""

    def __init__(self, tasks: Sequence[Task]) -> None:
        self._tasks = tasks

    def run(self) -> None:
        """Run all tasks sequentially."""
        for task in self._tasks:
            task.run()

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Start all tasks watching. Cleans up all on exit."""
        with ExitStack() as stack:
            for task in self._tasks:
                stack.enter_context(task.start_watching())
            yield
