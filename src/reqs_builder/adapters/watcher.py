"""Watcher — observe paths and invoke callback on changes."""

from collections.abc import Callable, Sequence
from pathlib import Path

from watchfiles import watch


class Watcher:
    """Watch paths and invoke callback on each debounced change set."""

    def __init__(
        self,
        watch_paths: Sequence[Path],
        on_change: Callable[[], object],
        *,
        debounce: int = 300,
    ) -> None:
        self._watch_paths = watch_paths
        self._on_change = on_change
        self._debounce = debounce

    def run(self) -> None:
        """Block and watch. Calls on_change for each debounced change set."""
        for _changes in watch(*self._watch_paths, debounce=self._debounce):
            self._on_change()
