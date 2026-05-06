"""CLI entry point."""

import sys
from pathlib import Path

import typer

from another_mood.config import ConfigValidationError, ProjectConfig
from another_mood.components.scaffold import blueprints as bp
from another_mood.pipeline.stages import pipeline

app = typer.Typer()
blueprint_app = typer.Typer(help="Manage built-in blueprints (sample projects).")
app.add_typer(blueprint_app, name="blueprint")


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


@blueprint_app.command("list")
def list_blueprints() -> None:
    """List available blueprints."""
    for name, description in bp.available_blueprints().items():
        print(name)
        print(f"  {description}")


@blueprint_app.command("apply")
def apply_blueprint(
    name: str = typer.Argument(help="Blueprint name."),
    project_dir: str = typer.Argument(help="Project directory."),
) -> None:
    """Apply a blueprint into a project directory."""
    blueprints = bp.available_blueprints()
    if name not in blueprints:
        print(
            f"unknown blueprint: {name!r} (available: {', '.join(blueprints)})",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    target = Path(project_dir)
    print(f"Scaffolding {target}/ from blueprint: {name}", file=sys.stderr)
    if not bp.apply_blueprint(name, target):
        raise typer.Exit(1)


@app.command()
def init(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Initialize a new project. Shortcut for `mood blueprint apply starter`."""
    apply_blueprint(bp.DEFAULT_BLUEPRINT, project_dir)


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
    port: int = typer.Option(5077, help="Preview server port"),
) -> None:
    """Watch for changes and rebuild automatically with live preview."""
    config = _load_config(project_dir=Path(project_dir), port=port)
    with pipeline(config).start_watching() as shutdown:
        try:
            print("Press Ctrl+C to stop.", file=sys.stderr, flush=True)
            shutdown.wait()
        except KeyboardInterrupt:
            pass


def main() -> None:
    app()
