"""Hugo adapter — low-level Hugo subprocess operations."""

import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import hugo.cli as _hugo_cli  # pyright: ignore[reportMissingTypeStubs]

_HUGO_SOURCE_DIR = files("another_mood.resources") / "hugo"
# Resolve the bundled Hugo binary directly. `uv tool install` exposes only
# entry-point shims on PATH, so a bare `["hugo", ...]` would not find the
# binary inside the tool's isolated environment.
_hugo_path = Path(_hugo_cli.__file__).parent / _hugo_cli.HUGO_BINARY_PATH
if not _hugo_path.is_file():
    raise FileNotFoundError(f"Bundled Hugo binary not found at {_hugo_path}")
_HUGO = str(_hugo_path)


def build(content_dir: Path, out_dir: Path, static_dir: Path) -> None:
    """Run Hugo build to generate static HTML."""
    subprocess.run(
        [
            _HUGO,
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(content_dir.resolve()),
            "--destination",
            str(out_dir.resolve()),
            "--logLevel",
            "error",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        env=_hugo_env(static_dir),
    )


@dataclass(frozen=True)
class Server:
    """A running Hugo dev server whose stderr is held back, not shown."""

    process: subprocess.Popen[str]
    _tail: deque[str]
    _drain: threading.Thread

    def stderr_tail(self) -> str:
        """The last lines Hugo wrote to stderr. Complete only once the
        process has exited."""
        self._drain.join(timeout=_DRAIN_JOIN_TIMEOUT)
        return "".join(self._tail).rstrip()


_STDERR_TAIL_LINES = 20
_DRAIN_JOIN_TIMEOUT = 1.0


def serve(content_dir: Path, host: str, port: int, static_dir: Path) -> Server:
    """Start Hugo dev server for live preview."""
    # stderr is held back rather than shown: the layouts are built in
    # (design/Trust model), so what Hugo reports while serving is not the
    # user's to act on. The one seen in practice is a spurious render error
    # when a rebuild lands mid-sync of prepare_site, which the next rebuild
    # clears. Real breakage still surfaces: hugo_build in `mood build` shows
    # Hugo's stderr, and the tail is kept for when the server dies.
    process = subprocess.Popen(
        [
            _HUGO,
            "server",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(content_dir.resolve()),
            "--bind",
            host,
            "--port",
            str(port),
            "--renderToMemory",
            "--logLevel",
            "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=_hugo_env(static_dir),
    )
    tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
    # The pipe must be read continuously, or Hugo blocks once it fills.
    drain = threading.Thread(target=_drain_stderr, args=(process, tail), daemon=True)
    drain.start()
    return Server(process=process, _tail=tail, _drain=drain)


def _hugo_env(static_dir: Path) -> dict[str, str]:
    """Env setting Hugo's static root to the blob dir (there is no --staticDir flag)."""
    return {**os.environ, "HUGO_STATICDIR": str(static_dir.resolve())}


def _drain_stderr(process: subprocess.Popen[str], tail: deque[str]) -> None:
    """Read Hugo's stderr to EOF, keeping only the last lines."""
    assert process.stderr is not None
    tail.extend(process.stderr)
