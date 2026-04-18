"""Watcher — observe paths and invoke callback on changes.

Thin wrapper over watchdog. Events within a burst are coalesced into a
single callback fire after `debounce` milliseconds of silence. See
internal/pipeline/pipeline.md for library-selection rationale.
"""

import sys
import threading
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class Watcher:
    """Watch paths and invoke callback on each debounced change set."""

    def __init__(
        self,
        watch_paths: Sequence[Path],
        on_change: Callable[[], object],
        *,
        debounce: int = 300,
    ) -> None:
        missing = [str(p) for p in watch_paths if not p.exists()]
        if missing:
            raise FileNotFoundError("Watch paths do not exist: " + ", ".join(missing))
        self._watch_paths = watch_paths
        self._on_change = on_change
        self._debounce_seconds = debounce / 1000.0

    def run(self) -> None:
        """Block and watch. Calls on_change for each debounced change set."""
        event_received = threading.Event()
        file_filter = {str(p) for p in self._watch_paths if p.is_file()}

        class _Handler(FileSystemEventHandler):
            # Only listen for mutation events. Ignoring open/access/close
            # prevents our own read of upstream from self-triggering the
            # watcher (inotify emits open/close events for reads, which
            # watchdog surfaces by default).
            #
            # When watching specific files (via parent dir), filter events
            # to avoid cross-talk from sibling files in the same directory.
            def _handle(self, event: FileSystemEvent) -> None:
                if not file_filter or event.src_path in file_filter:
                    event_received.set()

            on_created = _handle
            on_modified = _handle
            on_deleted = _handle
            on_moved = _handle

        handler = _Handler()
        observer = Observer()
        for path in self._watch_paths:
            if path.is_file():
                observer.schedule(handler, str(path.parent), recursive=False)
            else:
                observer.schedule(handler, str(path), recursive=True)
        observer.start()

        while True:
            event_received.wait()
            while True:
                event_received.clear()
                if not event_received.wait(self._debounce_seconds):
                    break
            try:
                self._on_change()
            except Exception:
                traceback.print_exc(file=sys.stderr)
