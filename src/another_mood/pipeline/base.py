"""Task — pipeline task base class, standard implementation, and composite."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from another_mood.components.shared.build_report import BuildReport
from another_mood.components.shared.component_output import ComponentOutput
from another_mood.pipeline.adapters.watcher import Watcher


class Task(ABC):
    """A unit of work with run (one-shot) and start_watching (dev mode)."""

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def start_watching(
        self, shutdown: threading.Event
    ) -> AbstractContextManager[None]: ...


@dataclass(frozen=True)
class Stage(Task):
    """Standard task: run function + Watcher."""

    run_fn: Callable[[], None]
    watch_paths: Sequence[Path]
    upstreams: Sequence[ComponentOutput] = ()

    def run(self) -> None:
        """Run the stage once."""
        self.run_fn()

    @contextmanager
    def start_watching(self, shutdown: threading.Event) -> Generator[None]:
        """Initial run + watch in background. Cleans up on exit."""
        self.run()

        if self.watch_paths:
            w = Watcher(self.watch_paths, self.run)
            threading.Thread(target=w.run, daemon=True).start()

        if self.upstreams:
            paths = [u.watch_target_path for u in self.upstreams]
            w = Watcher(paths, self.run, debounce=50)
            threading.Thread(target=w.run, daemon=True).start()

        yield


class ReportingStage(Stage):
    """Like Stage, but report_fn returns a BuildReport exposed via .report."""

    def __init__(
        self,
        report_fn: Callable[[], BuildReport],
        watch_paths: Sequence[Path] = (),
        upstreams: Sequence[ComponentOutput] = (),
    ) -> None:
        self._report_fn = report_fn
        self.report: BuildReport = BuildReport()
        super().__init__(
            run_fn=self._collect, watch_paths=watch_paths, upstreams=upstreams
        )

    def _collect(self) -> None:
        self.report = self._report_fn()


class Pipeline:
    """Composite task: runs a sequence of tasks as one."""

    def __init__(self, stages: Sequence[Task], reporting: ReportingStage) -> None:
        self._stages = stages
        self._reporting = reporting

    def run(self) -> BuildReport:
        """Run all stages then reporting. Return the build report."""
        for stage in self._stages:
            stage.run()
        self._reporting.run()
        return self._reporting.report

    @contextmanager
    def start_watching(self) -> Generator[threading.Event]:
        """Start all tasks watching. Yields shutdown event. Cleans up all on exit."""
        shutdown = threading.Event()
        with ExitStack() as stack:
            for task in [*self._stages, self._reporting]:
                stack.enter_context(task.start_watching(shutdown))
            yield shutdown
