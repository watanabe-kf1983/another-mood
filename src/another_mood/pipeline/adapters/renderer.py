"""Hugo renderer adapter — low-level Hugo subprocess operations."""

import subprocess
from importlib.resources import files
from pathlib import Path

_HUGO_SOURCE_DIR = files("another_mood.resources") / "hugo"


def build(content_dir: Path, out_dir: Path) -> None:
    """Run renderer build to generate static HTML."""
    subprocess.run(
        [
            "hugo",
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


def serve(content_dir: Path, port: int) -> subprocess.Popen[bytes]:
    """Start renderer dev server for live preview. Returns the Popen process."""
    return subprocess.Popen(
        [
            "hugo",
            "server",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(content_dir.resolve()),
            "--port",
            str(port),
            "--renderToMemory",
            "--logLevel",
            "error",
        ],
        stdout=subprocess.DEVNULL,
    )
