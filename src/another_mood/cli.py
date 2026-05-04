"""CLI entry point."""

import sys
from pathlib import Path

import typer

from another_mood.config import ConfigValidationError, ProjectConfig
from another_mood.components.scaffold.init import init_project
from another_mood.pipeline.stages import pipeline

app = typer.Typer()


@app.callback()
def callback() -> None:
    """Another Mood: a processor of source-based databases, keeping related documents in sync."""


def _load_config(**kwargs: object) -> ProjectConfig:
    """Build and verify ProjectConfig, exiting cleanly on validation failure."""
    config = ProjectConfig(**kwargs)  # type: ignore[arg-type]
    try:
        config.verify()
    except ConfigValidationError as exc:
        print(str(exc), file=sys.stderr)
        raise typer.Exit(1) from exc
    return config


@app.command()
def init(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Initialize a new project with sample directories and data."""
    target = Path(project_dir)
    print(f"Initializing project in {target}/", file=sys.stderr)
    if not init_project(target):
        raise typer.Exit(1)


@app.command()
def build(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Build the project to Markdown and rendered HTML."""
    config = _load_config(project_dir=Path(project_dir))
    report = pipeline(config).run()
    if report.has_errors():
        raise SystemExit(1)


@app.command()
def watch(
    project_dir: str = typer.Argument(help="Project directory"),
    port: int = typer.Option(1313, help="Hugo server port"),
) -> None:
    """Watch for changes and rebuild automatically with Hugo live preview."""
    config = _load_config(project_dir=Path(project_dir), port=port)
    with pipeline(config).start_watching() as shutdown:
        try:
            print("Press Ctrl+C to stop.", file=sys.stderr, flush=True)
            shutdown.wait()
        except KeyboardInterrupt:
            pass


def main() -> None:
    app()
