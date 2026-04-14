"""Watcher — observe paths and invoke callback on changes."""

import sys
import traceback
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
        missing = [str(p) for p in watch_paths if not p.exists()]
        if missing:
            raise FileNotFoundError("Watch paths do not exist: " + ", ".join(missing))
        self._watch_paths = watch_paths
        self._on_change = on_change
        self._debounce = debounce

    def run(self) -> None:
        """Block and watch. Calls on_change for each debounced change set."""
        for _changes in watch(*self._watch_paths, debounce=self._debounce):
            try:
                self._on_change()
            except Exception:
                traceback.print_exc(file=sys.stderr)
