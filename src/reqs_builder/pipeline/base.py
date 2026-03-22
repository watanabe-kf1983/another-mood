"""Stage — pipeline stage base class, standard implementation, and composite."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from pathlib import Path

from reqs_builder.adapters.watcher import Watcher
from reqs_builder.atomic_dir_writer import AtomicDirWriter, DirWriterFn


class Stage(ABC):
    """A pipeline stage with run (one-shot) and start_watching (dev mode)."""

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def start_watching(self) -> AbstractContextManager[None]: ...


class NormalStage(Stage):
    """Standard stage: AtomicDirWriter + Watcher."""

    def __init__(
        self,
        output_dir: Path,
        dir_writer_fn: DirWriterFn,
        watch_paths: Sequence[Path],
    ) -> None:
        self._output_dir = output_dir
        self._dir_writer_fn = dir_writer_fn
        self._watch_paths = watch_paths

    def run(self) -> None:
        """Run the stage once via AtomicDirWriter."""
        AtomicDirWriter(self._output_dir, self._dir_writer_fn).run()

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Initial run + watch in background. Cleans up on exit."""
        self.run()
        print("Build complete.", flush=True)

        thread = threading.Thread(
            target=lambda: Watcher(self._watch_paths, self._on_change).run(),
            daemon=True,
        )
        thread.start()
        yield

    def _on_change(self) -> None:
        self.run()
        print("Build complete.", flush=True)


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
