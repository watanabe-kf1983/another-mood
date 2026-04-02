"""CLI entry point."""

from pathlib import Path

import typer

from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.stages import pipeline

app = typer.Typer()


@app.callback()
def callback() -> None:
    """reqs-builder: a documentation build tool."""


@app.command()
def build(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Build the project (copy contents to output)."""
    config = ProjectConfig(project_dir=Path(project_dir))
    pipeline(config).run()
    print("Build completed.", flush=True)


@app.command()
def dev(
    project_dir: str = typer.Argument(help="Project directory"),
    port: int = typer.Option(1313, help="Hugo server port"),
) -> None:
    """Watch for changes and rebuild automatically with Hugo live preview."""
    import reqs_builder.context as ctx

    ctx.watch_mode = True
    config = ProjectConfig(project_dir=Path(project_dir), port=port)
    with pipeline(config).start_watching() as shutdown:
        try:
            print("Press Ctrl+C to stop.", flush=True)
            shutdown.wait()
        except KeyboardInterrupt:
            pass


def main() -> None:
    app()
