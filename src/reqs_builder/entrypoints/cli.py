"""CLI entry point."""

from pathlib import Path

import typer

from reqs_builder.config import ProjectConfig
from reqs_builder.entrypoints.build import build
from reqs_builder.entrypoints.dev import dev

app = typer.Typer()


@app.callback()
def callback() -> None:
    """reqs-builder: a documentation build tool."""


@app.command("build")
def build_command(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Build the project (copy contents to output)."""
    config = ProjectConfig(project_dir=Path(project_dir))
    build(config)


@app.command("dev")
def dev_command(
    project_dir: str = typer.Argument(help="Project directory"),
    port: int = typer.Option(1313, help="Hugo server port"),
) -> None:
    """Watch for changes and rebuild automatically with Hugo live preview."""
    config = ProjectConfig(project_dir=Path(project_dir), port=port)
    dev(config)


def main() -> None:
    app()
