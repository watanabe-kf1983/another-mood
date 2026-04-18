"""Render stage — prepare Hugo content and render to HTML."""

import signal
import subprocess
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from another_mood.pipeline.adapters import renderer
from another_mood.pipeline.adapters.watcher import Watcher
from another_mood.pipeline.base import Task


@dataclass(frozen=True)
class RenderStage(Task):
    """Render stage with Hugo-specific build/watch behavior."""

    src_dir: Path
    render_input_dir: Path
    render_dir: Path
    port: int

    def run(self) -> None:
        """Prepare content, then run renderer build."""
        prepared = self._prepare()
        renderer.build(prepared, self.render_dir)

    @contextmanager
    def start_watching(self, shutdown: threading.Event) -> Generator[None]:
        """Initial prepare + dev server + cascade watcher. Terminates server on exit."""
        prepared = self._prepare()
        process = renderer.serve(prepared, self.port)
        print(
            f"Server running at http://localhost:{self.port}/\n"
            f"  Auto-generated reference: http://localhost:{self.port}/__reference/",
            file=sys.stderr,
            flush=True,
        )

        cascade_watcher = Watcher([self.src_dir.parent], self._prepare, debounce=50)
        cascade = threading.Thread(target=cascade_watcher.run, daemon=True)
        cascade.start()

        monitor = threading.Thread(
            target=_wait_for_exit, args=(process, shutdown), daemon=True
        )
        monitor.start()

        try:
            yield
        finally:
            process.terminate()
            process.wait()

    def _prepare(self) -> Path:
        renderer.prepare(self.src_dir, self.render_input_dir)
        return self.render_input_dir


_NORMAL_EXIT_CODES = {0, -signal.SIGTERM, -signal.SIGINT}


def _wait_for_exit(process: subprocess.Popen[bytes], shutdown: threading.Event) -> None:
    """Wait for the process to exit and signal shutdown on unexpected termination.

    Normal exit codes:
    - 0: Hugo handles SIGINT (Ctrl+C) gracefully and exits 0
    - -SIGTERM (-15): our own terminate() call during shutdown
    - -SIGINT (-2): SIGINT before Hugo's handler runs
    """
    process.wait()
    if process.returncode in _NORMAL_EXIT_CODES:
        pass  # Normal shutdown (Ctrl+C or our terminate() call).
    else:
        print(
            f"Hugo server exited (exit code {process.returncode}).",
            file=sys.stderr,
            flush=True,
        )
        shutdown.set()
