"""Render stage — prepare Hugo content and render to HTML."""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial

from reqs_builder.adapters.renderer import hugo_build, hugo_server, prepare_hugo_content
from reqs_builder.adapters.watcher import Watcher
from reqs_builder.atomic_dir_writer import AtomicDirWriter
from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.base import Stage


class RenderStage(Stage):
    """Render stage with Hugo-specific build/watch behavior."""

    def __init__(self, config: ProjectConfig) -> None:
        self._config = config

    def run(self) -> None:
        """Prepare Hugo content via AtomicDirWriter, then run Hugo build."""
        c = self._config
        _prepare(c)
        hugo_build(c.hugo_content_dir, c.render_out_dir)

    @contextmanager
    def start_watching(self) -> Generator[None]:
        """Initial prepare + Hugo server + cascade watcher. Terminates server on exit."""
        c = self._config
        _prepare(c)
        process = hugo_server(c.hugo_content_dir, c.port)
        print(f"Hugo server started on http://localhost:{c.port}/", flush=True)

        cascade = threading.Thread(
            target=lambda: Watcher([c.out_dir], lambda: _prepare(c)).run(),
            daemon=True,
        )
        cascade.start()

        try:
            yield
        finally:
            process.terminate()
            process.wait()


def _prepare(config: ProjectConfig) -> None:
    AtomicDirWriter(
        config.hugo_content_dir,
        partial(prepare_hugo_content, config.out_dir),
    ).run()
