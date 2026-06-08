"""Hugo renderer adapter — low-level Hugo subprocess operations."""

import subprocess
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


def build(content_dir: Path, out_dir: Path) -> None:
    """Run renderer build to generate static HTML."""
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
    )


def serve(content_dir: Path, host: str, port: int) -> subprocess.Popen[bytes]:
    """Start renderer dev server for live preview. Returns the Popen process."""
    return subprocess.Popen(
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
    )
