"""Render stage — prepare Hugo content and render to HTML."""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from reqs_builder.pipeline.adapters import renderer
from reqs_builder.pipeline.adapters.watcher import Watcher
from reqs_builder.pipeline.base import Task


@dataclass(frozen=True)
class RenderStage(Task):
    """Render stage with Hugo-specific build/watch behavior."""

    src_dir: Path
    render_input_dir: Path
    render_output_dir: Path
    port: int

    def run(self) -> None:
        """Prepare content, then run renderer build."""
        prepared = self._prepare()
        renderer.build(prepared, self.render_output_dir)

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Initial prepare + dev server + cascade watcher. Terminates server on exit."""
        prepared = self._prepare()
        process = renderer.serve(prepared, self.port)
        print(f"Renderer started on http://localhost:{self.port}/", flush=True)

        cascade = threading.Thread(
            target=lambda: Watcher([self.src_dir], self._prepare).run(),
            daemon=True,
        )
        cascade.start()

        try:
            yield
        finally:
            process.terminate()
            process.wait()

    def _prepare(self) -> Path:
        renderer.prepare(self.src_dir, self.render_input_dir)
        return self.render_input_dir
