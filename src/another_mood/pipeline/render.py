"""Render stage — prepare Hugo content and render to HTML."""

import signal
import subprocess
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

from another_mood.components.shared.component.component import Component
from another_mood.pipeline.base import ComponentOutput
from another_mood.components.shared.component.errors import error_propagation
from another_mood.pipeline.adapters import renderer
from another_mood.pipeline.adapters.preparation import prepare_render
from another_mood.pipeline.base import MultiStageTask, Stage, Task

_logger = getLogger(__name__)

_STARTUP_PROBE_TIMEOUT = 0.5


class HugoServerStartupError(RuntimeError):
    """Hugo dev server died before reaching ready state (e.g. address in use)."""

    def __init__(self, host: str, port: int, returncode: int) -> None:
        super().__init__(
            f"Hugo server failed to start on {host}:{port} (exit code {returncode})."
        )
        self.host = host
        self.port = port
        self.returncode = returncode


@Component(
    out_dir="out_dir",
    upstream_dirs=["prep_dir"],
    error_propagation=False,
)
def hugo_build(prep_dir: Path, *, out_dir: Path) -> None:
    """Run Hugo build. Runs even on upstream error to render the __build_failure page."""
    with error_propagation([prep_dir], out_dir, component="hugo_build") as data_dirs:
        if data_dirs is not None:
            renderer.build(data_dirs.upstreams[0], data_dirs.out)
        else:
            renderer.build(prep_dir / "data", out_dir / "data")


def RenderStage(
    *,
    upstream: ComponentOutput,
    prep_dir: Path,
    hugo_build_dir: Path,
    host: str,
    port: int,
) -> MultiStageTask:
    """Compose the render pipeline: prep Stage + Hugo serve Task + Hugo build Stage."""
    prep_out = ComponentOutput(prep_dir)
    prep_call = prepare_render.bind(data_dir=upstream.dir, out_dir=prep_dir)
    hugo_build_call = hugo_build.bind(prep_dir=prep_dir, out_dir=hugo_build_dir)
    content_dir = prep_dir / "data"

    return MultiStageTask(
        [
            Stage(run_fn=prep_call, watch_paths=[], upstreams=[upstream]),
            Stage(run_fn=hugo_build_call, watch_paths=[], upstreams=[prep_out]),
            _HugoServeTask(content_dir=content_dir, host=host, port=port),
        ]
    )


@dataclass(frozen=True)
class _HugoServeTask(Task):
    """Hugo dev server. No-op in build mode (`hugo build` handles HTML output)."""

    content_dir: Path
    host: str
    port: int

    def run(self) -> None:
        pass

    @contextmanager
    def start_watching(self, shutdown: threading.Event) -> Generator[None]:
        process = renderer.serve(self.content_dir, self.host, self.port)

        # Surface fast-fail startup errors (e.g. port already in use) before
        # signalling readiness; Hugo binds the port synchronously at startup.
        try:
            process.wait(timeout=_STARTUP_PROBE_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass  # Still running — startup succeeded.
        else:
            raise HugoServerStartupError(self.host, self.port, process.returncode)

        monitor = threading.Thread(
            target=_wait_for_exit, args=(process, shutdown), daemon=True
        )
        monitor.start()

        try:
            yield
        finally:
            process.terminate()
            process.wait()


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
        _logger.error("Hugo server exited (exit code %d).", process.returncode)
        shutdown.set()
