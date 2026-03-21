"""Hugo renderer adapter — bridges reqs-builder pipeline to Hugo."""

import subprocess
from importlib.resources import files

from reqs_builder.config import ProjectPaths

_HUGO_SOURCE_DIR = files("reqs_builder.resources") / "hugo"


def render_build(paths: ProjectPaths) -> None:
    """Run hugo build to generate static HTML from outDir to render_out_dir."""
    assert paths.out_dir is not None
    assert paths.render_out_dir is not None

    subprocess.run(
        [
            "hugo",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(paths.out_dir.resolve()),
            "--destination",
            str(paths.render_out_dir.resolve()),
        ],
        check=True,
    )


def render_dev(paths: ProjectPaths, port: int) -> subprocess.Popen[bytes]:
    """Start hugo server for live preview. Returns the Popen process."""
    assert paths.out_dir is not None

    return subprocess.Popen(
        [
            "hugo",
            "server",
            "--source",
            str(_HUGO_SOURCE_DIR),
            "--contentDir",
            str(paths.out_dir.resolve()),
            "--port",
            str(port),
        ],
    )
