"""Watcher — observe paths and invoke callback on changes.

Thin wrapper over watchdog. Events within a burst are coalesced into a
single callback fire after `debounce` milliseconds of silence. Only content
changes fire: reading the watched tree never does, on any OS.
"""

import sys
import threading
from collections.abc import Callable, Sequence
from logging import getLogger
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

_logger = getLogger(__name__)


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
        if sys.platform == "win32":
            _request_content_changes_only()

        class _Handler(FileSystemEventHandler):
            # Only mutation events. Ignoring open/access/close prevents our own
            # read of the watched tree from self-triggering (inotify emits
            # open/close on reads, which watchdog surfaces by default).
            #
            # ``restrict_to`` is per handler: ``None`` (no restriction) for a
            # recursively-watched directory, where every event counts; or the
            # single file watched via its parent directory (watchdog can only
            # watch directories), so a sibling changing there does not fire.
            # Keeping the restriction per handler is the fix for the earlier
            # bug where one shared filter went non-empty as soon as any file
            # was watched and then suppressed the watched directories' events.
            def __init__(self, restrict_to: set[str] | None = None) -> None:
                self._restrict_to = restrict_to

            def _handle(self, event: FileSystemEvent) -> None:
                if self._restrict_to is None or event.src_path in self._restrict_to:
                    event_received.set()

            def _handle_modified(self, event: FileSystemEvent) -> None:
                # A directory's own "modified" is dropped: Windows reports one
                # when the directory is merely listed (its last-write flag
                # fires), and a real change inside it also reports the entry
                # that changed, on every OS.
                if not event.is_directory:
                    self._handle(event)

            on_created = _handle
            on_modified = _handle_modified
            on_deleted = _handle
            on_moved = _handle

        observer = Observer()
        for path in self._watch_paths:
            if path.is_file():
                observer.schedule(
                    _Handler(restrict_to={str(path)}),
                    str(path.parent),
                    recursive=False,
                )
            else:
                observer.schedule(_Handler(), str(path), recursive=True)
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
                _logger.exception("Watcher on_change handler raised")


def _request_content_changes_only() -> None:
    """Narrow the notifications watchdog requests from Windows to content changes."""
    from watchdog.observers import winapi

    # watchdog requests every notify flag and reports each hit as "modified".
    # Its LAST_ACCESS fires on every hardlink taken from a file, which is how
    # exclusive_read copies an upstream, so each stage retriggered itself.
    # watchdog reads this module constant at each ReadDirectoryChangesW call
    # and offers no setting, hence the replacement in place.
    if not hasattr(winapi, "WATCHDOG_FILE_NOTIFY_FLAGS"):
        raise RuntimeError(
            "watchdog.observers.winapi.WATCHDOG_FILE_NOTIFY_FLAGS is gone; "
            "without it, reads of a watched tree would trigger rebuilds."
        )
    winapi.WATCHDOG_FILE_NOTIFY_FLAGS = (
        winapi.FILE_NOTIFY_CHANGE_FILE_NAME
        | winapi.FILE_NOTIFY_CHANGE_DIR_NAME
        | winapi.FILE_NOTIFY_CHANGE_SIZE
        | winapi.FILE_NOTIFY_CHANGE_LAST_WRITE
    )
